#!/usr/bin/env python3
"""Offline end-to-end check: runs the roster -> gradebook -> attendance ->
PDF pipeline against canned fixture data (no live FACTS credentials
needed) and asserts the numbers come out right. Also useful as a way to
preview what the PDF layout looks like before you have real API access.

Run: python scripts/smoke_test.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.aggregator import build_student_report
from facts_progress.config import AttendanceCodeMap, Settings
from facts_progress.gradebook import load_reference_data
from facts_progress.pdf_report import build_student_pdf, output_filename
from facts_progress.roster import fetch_roster
from facts_progress.tests import fixtures
from facts_progress.tests.fake_client import FakeFactsClient


def make_settings() -> Settings:
    return Settings(
        subscription_key="fake",
        api_key="fake",
        api_version="1",
        base_url="https://example.invalid",
        school_id=fixtures.SCHOOL_ID,
        school_code=fixtures.SCHOOL_CODE,
        attendance_codes=AttendanceCodeMap(
            tardy_codes={"T"}, absent_codes={"A", "U"}, cut_codes={"C"}, ignored_codes={"P"}
        ),
    )


def main() -> int:
    client = FakeFactsClient()
    settings = make_settings()
    as_of = dt.date.fromisoformat(fixtures.AS_OF_DATE)
    term = _get_term(client, settings)

    students = fetch_roster(client, settings.school_code, grade_level="09")
    assert len(students) == 2, f"expected 2 enrolled grade-09 students, got {len(students)}"
    assert all(s.student_id != 10999 for s in students), "withdrawn student should be filtered out"
    assert all(s.student_id != 10888 for s in students), "Admissions (applicant) student should be filtered out"
    names = {s.student_id: (s.first_name, s.last_name) for s in students}
    assert names[10321] == ("Ari", "Blumenthal"), names
    assert names[10455] == ("Shira", "Katz"), "a name the batched lookup misses must be found one-at-a-time"

    one = fetch_roster(client, settings.school_code, student_ids={10321})
    assert [s.student_id for s in one] == [10321] and one[0].last_name == "Blumenthal", one
    assert fetch_roster(client, settings.school_code, student_ids={10999}) == [], "withdrawn student by id must be skipped"
    everyone = fetch_roster(client, settings.school_code)
    assert {s.student_id for s in everyone} == {10321, 10455, 10500}, "only Enrolled students"

    ref = load_reference_data(client, settings.school_code)
    assert ref.courses_by_id[801]["title"] == "Algebra I"
    assert ref.course_levels_by_id[1] == "Honors"

    output_dir = Path(__file__).resolve().parent.parent / "output" / "smoke_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    for student in students:
        report = build_student_report(client, settings, ref, student, term, as_of)
        reports.append(report)

        path = output_dir / output_filename(report)
        build_student_pdf(report, "Sample Academy", path)
        print(f"wrote {path} ({path.stat().st_size} bytes)")

    ari = next(r for r in reports if r.student.student_id == 10321)
    ari_by_course = {c.course_name: c for c in ari.classes}
    assert set(ari_by_course) == {"Algebra I", "English 9"}, ari_by_course
    assert ari_by_course["Algebra I"].numeric_grade == 88.4, "should use MP2 grade, not full-year row"
    assert ari_by_course["Algebra I"].course_level == "Honors"
    assert ari_by_course["Algebra I"].tardies == 2, "the Dec 1 tardy is outside the as-of window and must not count"
    assert ari_by_course["English 9"].absences == 1
    assert ari_by_course["English 9"].cuts == 1

    shira = next(r for r in reports if r.student.student_id == 10455)
    shira_by_course = {c.course_name: c for c in shira.classes}
    assert shira_by_course["Chumash"].numeric_grade is None, "blank average + fullAverage 0 -> should be None, not 0.0"
    assert shira_by_course["Chumash"].cuts == 2

    _check_batch_behaviour(client, settings, term, as_of)
    _check_retry_wait()
    _check_rate_limiter()

    print("\nAll smoke-test assertions passed.")
    print(f"Sample PDFs written to: {output_dir}")
    return 0


def _check_batch_behaviour(client, settings, term, as_of):
    """One student's FACTS failure must not stop the others, and skip must work."""
    from facts_progress.aggregator import iter_reports
    from facts_progress.facts_client import FactsApiError

    class FlakyClient(FakeFactsClient):
        def get_paged(self, path, filters=None, **kw):
            if path == "/Classes/v2/Students/10455":
                raise FactsApiError(500, "boom", path)
            yield from super().get_paged(path, filters=filters, **kw)

    out = list(iter_reports(FlakyClient(), settings, term, grade_level="09", as_of=as_of))
    by_id = {s.student_id: (r, e) for s, r, e in out}
    assert by_id[10321][0] is not None and by_id[10321][1] is None, "healthy student must still be built"
    assert by_id[10455][0] is None and by_id[10455][1] is not None, "failing student must be reported, not crash the run"

    out = list(iter_reports(client, settings, term, grade_level="09", as_of=as_of,
                            skip=lambda s: s.student_id == 10321))
    by_id = {s.student_id: (r, e) for s, r, e in out}
    assert by_id[10321] == (None, None), "skipped student yields (None, None)"
    assert by_id[10455][0] is not None


def _check_retry_wait():
    from facts_progress.facts_client import _retry_wait

    class R:
        def __init__(self, h): self.headers = h
    assert _retry_wait(1, R({"Retry-After": "7"})) == 7.0, "must honor Retry-After"
    assert _retry_wait(1, R({"Retry-After": "9999"})) == 60, "Retry-After is capped"
    assert _retry_wait(1, R({})) == 1.5 and _retry_wait(3, R({})) == 6.0, "exponential backoff without the header"
    assert _retry_wait(20) == 60, "backoff is capped"


def _check_rate_limiter():
    from facts_progress.facts_client import _paced_limits
    assert _paced_limits(10, 100) == (8, 90), _paced_limits(10, 100)
    assert _paced_limits(10, 600) == (8, 540), _paced_limits(10, 600)
    """With a fake clock: 500 back-to-back requests must never put more than
    8 in any 1-second window or more than 90 in any 60-second window."""
    from facts_progress.facts_client import _RateLimiter

    now = [0.0]
    sleeps = []

    def sleep(d):
        sleeps.append(d)
        now[0] += d

    lim = _RateLimiter(8, 90, clock=lambda: now[0], sleep=sleep)
    stamps = []
    for _ in range(500):
        lim.wait()
        stamps.append(now[0])
    for i, t in enumerate(stamps):
        in_sec = sum(1 for u in stamps[: i + 1] if t - u < 1)
        in_min = sum(1 for u in stamps[: i + 1] if t - u < 60)
        assert in_sec <= 8, f"{in_sec} requests within 1s at t={t}"
        assert in_min <= 90, f"{in_min} requests within 60s at t={t}"
    assert stamps[-1] >= 5 * 60 - 60, "500 requests at <=90/min cannot finish faster than ~5 minutes"


def _get_term(client, settings):
    from facts_progress.terms import NoActiveTermError, get_current_term, get_term_by_id

    # Term ids repeat every school year: a bare term id must be refused as
    # ambiguous rather than silently picking one year's term.
    try:
        get_term_by_id(client, settings.school_id, fixtures.TERM_ID)
    except NoActiveTermError:
        pass
    else:
        raise AssertionError("a term id that exists in two school years must be refused as ambiguous")

    term = get_term_by_id(client, settings.school_id, fixtures.TERM_ID, fixtures.YEAR_ID)
    assert term.year_id == fixtures.YEAR_ID, term

    # Auto-detection must land on the current year's term, not last year's.
    auto = get_current_term(client, settings.school_id, as_of=dt.date.fromisoformat(fixtures.AS_OF_DATE))
    assert (auto.term_id, auto.year_id) == (fixtures.TERM_ID, fixtures.YEAR_ID), auto
    return term


if __name__ == "__main__":
    sys.exit(main())