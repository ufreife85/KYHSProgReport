"""Pulls course/level/numeric-grade info for a student's classes.

Design note on filtering: the OpenAPI spec documents every list endpoint
as "Sieve filtering" but doesn't publish the exact property paths Sieve
is configured with for nested reference fields (e.g. is a student id
filtered as `studentId==123` or `studentReference.studentId==123`?).
To stay correct regardless of exactly how your FACTS instance has Sieve
configured, every fetch here sends its best-guess filter (to keep
response sizes small) but then ALWAYS re-checks the relevant id fields
client-side before using a row. If you find the server-side filters
aren't narrowing anything (check the logs -- a DEBUG line logs how many
raw rows came back), that's fine, just slower; the results will still
be correct.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .facts_client import FactsClient

logger = logging.getLogger(__name__)


@dataclass
class ReferenceData:
    """School-wide lookup tables, fetched once per run and reused for
    every student."""
    courses_by_id: dict[int, dict] = field(default_factory=dict)          # courseID -> {"title", "levelID"}
    course_levels_by_id: dict[int, str] = field(default_factory=dict)      # courseLevelID -> levelName


def load_reference_data(client: FactsClient, school_code: str) -> ReferenceData:
    ref = ReferenceData()

    for row in client.get_paged("/Courses", filters=f"schoolCode=={school_code}"):
        if (row.get("schoolCode") or "").strip().lower() != school_code.strip().lower():
            continue
        ref.courses_by_id[row["courseID"]] = {
            "title": row.get("title") or row.get("abbreviation") or f"Course {row['courseID']}",
            "levelID": row.get("levelID"),
        }

    for row in client.get_paged("/Gradebooks/CourseLevel"):
        level_id = row.get("courseLevelID")
        if level_id is not None:
            ref.course_levels_by_id[level_id] = row.get("levelName") or ""

    logger.debug(
        "Loaded reference data: %d courses, %d course levels",
        len(ref.courses_by_id), len(ref.course_levels_by_id),
    )
    return ref


def fetch_student_classes(client: FactsClient, student_id: int) -> dict[int, dict]:
    """Returns classId -> {"courseID", "name", "section"} for every class
    the student is scheduled into (any term)."""
    classes: dict[int, dict] = {}
    for row in client.get_paged(f"/Classes/v2/Students/{student_id}"):
        class_id = row.get("classId")
        if class_id is None:
            continue
        classes[class_id] = {
            "courseID": row.get("courseID"),
            "name": row.get("name"),
            "section": row.get("section"),
        }
    return classes


def _numeric_grade(row: dict) -> float | None:
    """Extracts a numeric grade from a GbkSummary row. Prefers the
    `average` field (the course's displayed average, already rounded to
    that course level's configured decimal places); falls back to
    `fullAverage` (the unrounded value) if `average` isn't a plain
    number (e.g. blank, or a pass/fail-style display value).
    """
    raw_avg = row.get("average")
    if raw_avg not in (None, ""):
        try:
            return float(raw_avg)
        except (TypeError, ValueError):
            pass
    # fullAverage appears to default to 0 when FACTS hasn't computed an
    # average yet (e.g. an incomplete/no-grades-entered class), so a
    # bare 0 with no `average` string is treated as "no grade" rather
    # than a literal zero. If your school's classes can legitimately
    # average to 0, remove this guard.
    full_avg = row.get("fullAverage")
    if full_avg not in (None, "", 0):
        try:
            return float(full_avg)
        except (TypeError, ValueError):
            pass
    return None


def fetch_grades_for_student(client: FactsClient, student_id: int, term_id: int) -> dict[int, float | None]:
    """Returns classId -> numeric_grade for a student's grades in the
    given term, pulled from GbkSummary.
    """
    grades: dict[int, float | None] = {}
    raw_count = 0
    for row in client.get_paged("/Gradebooks/GbkSummary", filters=f"studentId=={student_id}"):
        raw_count += 1
        row_student_id = ((row.get("studentReference") or {}).get("studentId"))
        row_term_id = ((row.get("termReference") or {}).get("termId"))
        row_class_id = ((row.get("classReference") or {}).get("classId"))

        if row_student_id != student_id or row_term_id != term_id or row_class_id is None:
            continue

        grades[row_class_id] = _numeric_grade(row)

    logger.debug(
        "GbkSummary: %d raw rows for student %d, %d matched term %d",
        raw_count, student_id, len(grades), term_id,
    )
    return grades


def class_course_info(ref: ReferenceData, class_info: dict) -> tuple[str, str]:
    """Resolves (course_name, course_level) for one class's raw
    courseID, given the school-wide reference data."""
    course_id = class_info.get("courseID")
    course = ref.courses_by_id.get(course_id, {})
    course_name = course.get("title") or class_info.get("name") or "Unknown Course"
    level_name = ref.course_levels_by_id.get(course.get("levelID"), "") or ""
    return course_name, level_name
