"""Fetches the student roster (demographics) from FACTS.

Filtering by grade level / homeroom / active status is done client-side
after pulling the school's roster, rather than trying to guess FACTS's
exact Sieve filter property paths for nested fields -- the roster for a
single school is small enough that this is simple and reliable. If your
school is very large, you can tighten `filters` in `fetch_roster` once
you've confirmed the right Sieve syntax for your instance (the
--list-raw-student CLI flag can help you inspect one record's shape).
"""
from __future__ import annotations

import logging

from .facts_client import FactsClient
from .models import StudentDemographics

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"active"}


def fetch_roster(
    client: FactsClient,
    school_code: str,
    grade_level: str | None = None,
    homeroom: str | None = None,
    student_ids: set[int] | None = None,
    active_only: bool = True,
) -> list[StudentDemographics]:
    """Returns demographics for students matching the given filters.

    grade_level: exact match against the student's school.gradeLevel
                 (e.g. "09", "9", "K" -- match whatever your FACTS grade
                 level codes look like; comparison is case-insensitive
                 and whitespace-trimmed).
    homeroom: exact match against the student's homeroom field.
    student_ids: if given, restrict to just these FACTS student ids
                 (used for --student on the CLI).
    """
    students: list[StudentDemographics] = []

    for row in client.get_paged("/Students", filters=f"schoolCode=={school_code}"):
        school = row.get("school") or {}
        status = (school.get("status") or "").strip().lower()
        if active_only and status not in ACTIVE_STATUSES:
            continue

        row_grade = (school.get("gradeLevel") or "").strip()
        if grade_level and row_grade.lower() != grade_level.strip().lower():
            continue

        row_homeroom = (row.get("homeroom") or "").strip()
        if homeroom and row_homeroom.lower() != homeroom.strip().lower():
            continue

        sid = row.get("studentId")
        if student_ids and sid not in student_ids:
            continue

        person = ((row.get("demographics") or {}).get("person")) or {}

        students.append(
            StudentDemographics(
                student_id=sid,
                person_id=person.get("personId"),
                first_name=person.get("firstName") or "",
                last_name=person.get("lastName") or "",
                grade_level=row_grade,
                homeroom=row_homeroom,
            )
        )

    students.sort(key=lambda s: (s.last_name.lower(), s.first_name.lower()))
    return students
