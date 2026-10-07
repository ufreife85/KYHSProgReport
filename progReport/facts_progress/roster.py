"""Fetches the student roster from FACTS.

How the real FACTS data is shaped (confirmed against your live account):

  * /Students gives studentId, status, grade level and a personStudentId --
    but NO names.
  * Names come from /People. A student's personId is the same number as
    their studentId (NOT personStudentId -- that one 404s). This is the same
    approach the AT Tracker sheet uses.
  * "Current student" means school.status == "Enrolled". (Other statuses seen:
    Admissions, Withdrawn, Graduate, Inactive -- all excluded.)
  * FACTS accepts a server-side filter `studentId==N` on /Students, so
    --student runs don't have to read all ~2,900 records.

Grade level is filtered client-side after the roster is read.
"""
from __future__ import annotations

import logging

from .facts_client import FactsApiError, FactsClient
from .models import StudentDemographics

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"enrolled"}

# How many students to look up per /People request ("personId==1|2|3...").
PEOPLE_BATCH_SIZE = 40


def fetch_roster(
    client: FactsClient,
    school_code: str,
    grade_level: str | None = None,
    student_ids: set[int] | None = None,
    active_only: bool = True,
) -> list[StudentDemographics]:
    """Returns students matching the given filters, with names filled in.

    grade_level: exact match against the student's school.gradeLevel
                 (case-insensitive, whitespace-trimmed).
    student_ids: if given, restrict to just these FACTS student ids
                 (used for --student on the CLI).
    active_only: keep only students whose status is "Enrolled".
    """
    if student_ids:
        rows = []
        for sid in sorted(student_ids):
            found = [r for r in client.get_paged("/Students", filters=f"studentId=={sid}")
                     if r.get("studentId") == sid]
            if not found:
                logger.warning("Student id %s was not found in FACTS.", sid)
            rows.extend(found)
    else:
        rows = list(client.get_paged("/Students", filters=f"schoolCode=={school_code}"))

    kept: list[tuple[int, str]] = []
    for row in rows:
        school = row.get("school") or {}
        status = (school.get("status") or "").strip().lower()
        sid = row.get("studentId")
        if active_only and status not in ACTIVE_STATUSES:
            if student_ids:
                logger.warning("Student id %s has status %r, not Enrolled -- skipped.", sid, school.get("status"))
            continue

        row_grade = (school.get("gradeLevel") or "").strip()
        if grade_level and row_grade.lower() != grade_level.strip().lower():
            continue

        kept.append((sid, row_grade))

    names = _fetch_names(client, [sid for sid, _ in kept])

    students = []
    for sid, row_grade in kept:
        first, last = names.get(sid, ("", ""))
        students.append(
            StudentDemographics(
                student_id=sid,
                person_id=sid,
                first_name=first,
                last_name=last,
                grade_level=row_grade,
            )
        )

    students.sort(key=lambda s: (s.last_name.lower(), s.first_name.lower(), s.student_id))
    return students


def _fetch_names(client: FactsClient, student_ids: list[int]) -> dict[int, tuple[str, str]]:
    """Returns {studentId: (firstName, lastName)}. Looks people up in batches
    by personId (== studentId); anyone a batch misses is retried one at a
    time via /People/{id}. Anyone still missing is logged and left blank."""
    names: dict[int, tuple[str, str]] = {}
    wanted = set(student_ids)

    for i in range(0, len(student_ids), PEOPLE_BATCH_SIZE):
        batch = student_ids[i:i + PEOPLE_BATCH_SIZE]
        flt = "personId==" + "|".join(str(s) for s in batch)
        for person in client.get_paged("/People", filters=flt):
            pid = person.get("personId")
            if pid in wanted:  # re-check client-side; never trust the filter alone
                names[pid] = _name_of(person)

    for sid in student_ids:
        if sid in names and any(names[sid]):
            continue
        try:
            names[sid] = _name_of(client.get_one(f"/People/{sid}", params={}))
        except FactsApiError as exc:
            logger.warning("No name found for student id %s (%s).", sid, exc)

    return names


def _name_of(person: dict) -> tuple[str, str]:
    return ((person.get("firstName") or "").strip(), (person.get("lastName") or "").strip())