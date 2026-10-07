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
    assert len(students) == 2, f"expected 2 active grade-09 students, got {len(students)}"
    assert all(s.student_id != 10999 for s in students), "withdrawn student should be filtered out"

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

    print("\nAll smoke-test assertions passed.")
    print(f"Sample PDFs written to: {output_dir}")
    return 0


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