"""A FactsClient stand-in that serves the canned fixtures instead of
making real HTTP calls, so the whole pipeline (roster -> gradebook ->
attendance -> PDF) can be exercised offline. See scripts/smoke_test.py.
"""
from __future__ import annotations

import re
from typing import Iterator

from . import fixtures

_STUDENT_CLASSES_RE = re.compile(r"^/Classes/v2/Students/(\d+)$")


class FakeFactsClient:
    """Duck-types the subset of FactsClient's interface the rest of the
    codebase calls: get_paged(path, filters=..., ...).
    """

    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []

    def get_paged(self, path: str, filters: str | None = None, **_kwargs) -> Iterator[dict]:
        self.calls.append((path, filters))

        if path == f"/SchoolTerms/v2/Schools/{fixtures.SCHOOL_ID}":
            yield from fixtures.TERMS["results"]
            return

        if path == "/Students":
            yield from fixtures.STUDENTS["results"]
            return

        if path == "/Courses":
            yield from fixtures.COURSES["results"]
            return

        if path == "/Gradebooks/CourseLevel":
            yield from fixtures.COURSE_LEVELS["results"]
            return

        if path == "/Academics/AttendanceCodes":
            yield from fixtures.ATTENDANCE_CODES["results"]
            return

        m = _STUDENT_CLASSES_RE.match(path)
        if m:
            student_id = int(m.group(1))
            yield from fixtures.CLASSES_BY_STUDENT.get(student_id, {}).get("results", [])
            return

        if path == "/Gradebooks/GbkSummary":
            student_id = _extract_student_id_filter(filters)
            yield from fixtures.GBK_SUMMARY_BY_STUDENT.get(student_id, {}).get("results", [])
            return

        if path == "/People/StudentAttendance":
            student_id = _extract_student_id_filter(filters)
            yield from fixtures.ATTENDANCE_BY_STUDENT.get(student_id, {}).get("results", [])
            return

        raise AssertionError(f"FakeFactsClient has no fixture for path: {path}")

    def get_one(self, path: str, params: dict | None = None) -> dict:
        """Duck-types FactsClient.get_one -- returns a single-page
        PagedResultOf-shaped envelope built from the same fixtures
        get_paged() serves, so scripts that call get_one() (e.g.
        scripts/check_setup.py's auth ping) can be exercised offline too.
        """
        filters = (params or {}).get("Filters")
        results = list(self.get_paged(path, filters=filters))
        return {
            "results": results,
            "currentPage": 1,
            "pageCount": 1,
            "pageSize": len(results),
            "rowCount": len(results),
            "nextPage": None,
        }


def _extract_student_id_filter(filters: str | None) -> int | None:
    if not filters:
        return None
    m = re.search(r"studentId==(\d+)", filters)
    return int(m.group(1)) if m else None
