#!/usr/bin/env python3
"""Read-only: for every course, how many CURRENTLY ENROLLED students are in it
this term -- and whether it would print on a progress report.

This answers "is anyone even in that class?" school-wide, using the same rules
as the report: Enrolled students only, enrolled in the class for the report
term, then split by whether the course is attendance-ON / attendance-OFF /
marked Activity.

Prints course titles, student COUNTS and grade levels only -- no names.
It reads: all current students, the school year's classes, the course list and
the enrollment records (roughly 50-150 FACTS requests; allow a couple of minutes).

Run: python scripts/course_enrollment_counts.py
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from facts_progress.gradebook import enrolled_in_term, load_reference_data
from facts_progress.roster import ACTIVE_STATUSES
from facts_progress.terms import NoActiveTermError, get_current_term


def count_by_course(enrollments: list[dict], class_to_course: dict[int, int],
                    roster: dict[int, str], term_id: int) -> dict[int, dict[int, str]]:
    """Pure function. {courseID: {studentId: gradeLevel}} for enrolled students
    (roster only) in classes of the year, enrolled in the report term."""
    out: dict[int, dict[int, str]] = collections.defaultdict(dict)
    for e in enrollments:
        sid, cid = e.get("studentId"), e.get("classId")
        if sid not in roster or cid not in class_to_course:
            continue
        if enrolled_in_term(e, term_id):
            out[class_to_course[cid]][sid] = roster[sid]
    return out


def classify(course: dict) -> str:
    """'print' | 'off' | 'activity' | 'unknown'-flag courses are kept, so they count as 'print'."""
    if course.get("activity") is True:
        return "activity"
    if course.get("attendance") is False:
        return "off"
    return "print"


def fetch_enrollments(client: FactsClient) -> list[dict]:
    """All enrollment rows. Tries the server-side filter enrolled==true first (far fewer
    rows); if FACTS rejects that filter, reads everything."""
    try:
        return list(client.get_paged("/Academics/Enrollments", filters="enrolled==true", page_size=1000))
    except FactsApiError as exc:
        print(f"(The enrolled==true filter was refused: {exc}. Reading all enrollment rows instead.)")
        return list(client.get_paged("/Academics/Enrollments", page_size=1000))


def main() -> int:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    try:
        term = get_current_term(client, settings.school_id)
        ref = load_reference_data(client, settings.school_code)

        roster: dict[int, str] = {}
        for row in client.get_paged("/Students", filters=f"schoolCode=={settings.school_code}", page_size=1000):
            school = row.get("school") or {}
            if (school.get("status") or "").strip().lower() in ACTIVE_STATUSES and row.get("studentId") is not None:
                roster[row["studentId"]] = (school.get("gradeLevel") or "?").strip()

        class_to_course = {}
        for row in client.get_paged(f"/Classes/v2/SchoolYears/{term.year_id}", page_size=1000):
            if row.get("classId") is not None:
                class_to_course[row["classId"]] = row.get("courseID")

        enrollments = fetch_enrollments(client)
    except (FactsApiError, NoActiveTermError) as exc:
        print(f"FACTS error: {exc}")
        return 1

    print(f"Term: {term.name} (year {term.year_id}, term {term.term_id}).  Enrolled students: {len(roster)}.  "
          f"Classes this year: {len(class_to_course)}.  Enrollment rows read: {len(enrollments)}.  "
          f"FACTS requests used: {client.request_count}\n")

    by_course = count_by_course(enrollments, class_to_course, roster, term.term_id)
    groups: dict[str, list[tuple]] = {"print": [], "off": [], "activity": []}
    for course_id, students in by_course.items():
        course = ref.courses_by_id.get(course_id, {"title": f"Course {course_id}"})
        grades = collections.Counter(students.values())
        grade_text = ", ".join(f"gr {g}: {n}" for g, n in sorted(grades.items()))
        groups[classify(course)].append((course.get("title", f"Course {course_id}"), course_id, len(students), grade_text))

    labels = {"print": "WOULD PRINT on reports (attendance on, not an activity)",
              "off": "NOT printed -- attendance OFF (students are enrolled)",
              "activity": "NOT printed -- marked Activity (students are enrolled)"}
    for key in ("print", "off", "activity"):
        rows = sorted(groups[key], key=lambda r: (r[0].lower(), r[1]))
        print(f"== {labels[key]}: {len(rows)} course(s) with students")
        for title, cid, n, grade_text in rows:
            print(f"  {title} [course {cid}] -- {n} student(s)   ({grade_text})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())