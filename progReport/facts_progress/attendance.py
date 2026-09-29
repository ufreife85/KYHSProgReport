"""Pulls and tallies per-class attendance (tardy/absent/cut) for a
student over a date range, using the code mapping in attendance_codes.json.

See the filtering note at the top of gradebook.py -- the same
best-guess-filter-then-verify-client-side pattern is used here.
"""
from __future__ import annotations

import datetime as dt
import logging

from dateutil import parser as dateparser

from .config import AttendanceCodeMap
from .facts_client import FactsClient

logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dateparser.parse(value).date()
    except (ValueError, TypeError):
        return None


def fetch_attendance_codes(client: FactsClient) -> dict[str, dict]:
    """Returns code -> {"name", "absent", "tardy", "excused"} for every
    attendance code configured in FACTS. Handy for `--list-attendance-codes`
    so you can confirm the values that belong in attendance_codes.json.
    """
    codes: dict[str, dict] = {}
    for row in client.get_paged("/Academics/AttendanceCodes"):
        code = row.get("code")
        if not code:
            continue
        codes[code] = {
            "name": row.get("name") or "",
            "absent": bool(row.get("absent")),
            "tardy": bool(row.get("tardy")),
            "excused": bool(row.get("excused")),
        }
    return codes


def tally_attendance_for_student(
    client: FactsClient,
    code_map: AttendanceCodeMap,
    student_id: int,
    start_date: dt.date,
    end_date: dt.date,
) -> dict[int, dict[str, int]]:
    """Returns classId -> {"tardies": n, "absences": n, "cuts": n} for
    every class with at least one tallied attendance event in range.
    Classes with zero events are simply absent from the dict (treat a
    missing key as all-zero).
    """
    tallies: dict[int, dict[str, int]] = {}
    raw_count = 0

    date_filter = (
        f"attendanceDate>={start_date.isoformat()},"
        f"attendanceDate<={end_date.isoformat()}"
    )
    filters = f"studentId=={student_id},{date_filter}"

    for row in client.get_paged("/People/StudentAttendance", filters=filters):
        raw_count += 1
        row_student_id = (row.get("studentReference") or {}).get("studentId")
        if row_student_id != student_id:
            continue

        event_date = _parse_date(row.get("attendanceDate"))
        if event_date is None or not (start_date <= event_date <= end_date):
            continue

        category = code_map.categorize(row.get("attendanceCode"))
        if category is None:
            continue

        class_id = (row.get("classReference") or {}).get("classId")
        if class_id is None:
            continue

        tally = tallies.setdefault(class_id, {"tardies": 0, "absences": 0, "cuts": 0})
        if category == "tardy":
            tally["tardies"] += 1
        elif category == "absent":
            tally["absences"] += 1
        elif category == "cut":
            tally["cuts"] += 1

    logger.debug(
        "StudentAttendance: %d raw rows for student %d between %s and %s, %d classes with tallies",
        raw_count, student_id, start_date, end_date, len(tallies),
    )
    return tallies
