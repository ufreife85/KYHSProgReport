"""Orchestrates pulling demographics + gradebook + attendance for a list
of students and assembling StudentReport objects -- one merged row per
class (course, level, numeric grade, tardies, absences, cuts).
"""
from __future__ import annotations

import datetime as dt
import logging

from .attendance import tally_attendance_for_student
from .config import Settings
from .facts_client import FactsClient
from .gradebook import (
    ReferenceData,
    class_course_info,
    fetch_grades_for_student,
    fetch_student_classes,
    load_reference_data,
)
from .models import ClassProgress, StudentDemographics, StudentReport, Term
from .roster import fetch_roster

logger = logging.getLogger(__name__)


def build_student_report(
    client: FactsClient,
    settings: Settings,
    ref: ReferenceData,
    student: StudentDemographics,
    term: Term,
    as_of: dt.date,
) -> StudentReport:
    student_classes = fetch_student_classes(client, student.student_id)
    grades_by_class = fetch_grades_for_student(client, student.student_id, term.term_id)

    term_start = _safe_date(term.first_day) or as_of
    term_end = min(as_of, _safe_date(term.last_day) or as_of)
    if term_end < term_start:
        term_end = term_start
    attendance_by_class = tally_attendance_for_student(
        client, settings.attendance_codes, student.student_id, term_start, term_end
    )

    # A row belongs in the report if the student has a computed grade
    # for this term in that class, and/or has tallied attendance events
    # in it -- this naturally excludes classes that don't meet this
    # term while still surfacing a class with attendance but no grade
    # entered yet (common early in a marking period).
    class_ids = set(grades_by_class) | set(attendance_by_class)

    rows = []
    for class_id in class_ids:
        class_info = student_classes.get(class_id, {})
        course_name, course_level = class_course_info(ref, class_info)
        tallies = attendance_by_class.get(class_id, {"tardies": 0, "absences": 0, "cuts": 0})

        rows.append(
            ClassProgress(
                class_id=class_id,
                course_name=course_name,
                course_level=course_level,
                numeric_grade=grades_by_class.get(class_id),
                tardies=tallies["tardies"],
                absences=tallies["absences"],
                cuts=tallies["cuts"],
            )
        )

    rows.sort(key=lambda r: r.course_name.lower())
    return StudentReport(student=student, term=term, classes=rows)


def build_reports(
    client: FactsClient,
    settings: Settings,
    term: Term,
    grade_level: str | None = None,
    homeroom: str | None = None,
    student_ids: set[int] | None = None,
    as_of: dt.date | None = None,
) -> list[StudentReport]:
    as_of = as_of or dt.date.today()

    students = fetch_roster(
        client,
        settings.school_code,
        grade_level=grade_level,
        homeroom=homeroom,
        student_ids=student_ids,
    )
    logger.info("Roster matched %d active student(s)", len(students))

    ref = load_reference_data(client, settings.school_code)

    reports = []
    for i, student in enumerate(students, start=1):
        logger.info(
            "[%d/%d] Building report for %s %s (student %s)",
            i, len(students), student.first_name, student.last_name, student.student_id,
        )
        reports.append(build_student_report(client, settings, ref, student, term, as_of))

    return reports


def _safe_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    from dateutil import parser as dateparser
    try:
        return dateparser.parse(value).date()
    except (ValueError, TypeError):
        return None
