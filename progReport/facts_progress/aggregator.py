"""Orchestrates pulling demographics + gradebook + attendance for a list
of students and assembling StudentReport objects -- one merged row per
class (course, level, numeric grade, tardies, absences, cuts).
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Callable, Iterator

from .attendance import tally_attendance_for_student
from .config import Settings
from .facts_client import FactsApiError, FactsClient
from .gradebook import (
    ReferenceData,
    class_course_info,
    classes_in_year,
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
    all_classes = fetch_student_classes(client, student.student_id)
    # Term ids repeat every school year, so only trust classes from the
    # report term's own year (see classes_in_year for the full reasoning).
    student_classes = classes_in_year(all_classes, term.year_id)
    if all_classes and not student_classes:
        logger.warning(
            "Student %s has %d class(es) but none with yearId == %s (the report term's year) -- "
            "the report will be empty. Run scripts/check_setup.py --student %s to inspect.",
            student.student_id, len(all_classes), term.year_id, student.student_id,
        )

    grades_by_class = {
        cid: grade
        for cid, grade in fetch_grades_for_student(client, student.student_id, term.term_id).items()
        if cid in student_classes
    }

    term_start = _safe_date(term.first_day) or as_of
    term_end = min(as_of, _safe_date(term.last_day) or as_of)
    if term_end < term_start:
        term_end = term_start
    attendance_by_class = {
        cid: tally
        for cid, tally in tally_attendance_for_student(
            client, settings.attendance_codes, student.student_id, term_start, term_end
        ).items()
        if cid in student_classes
    }

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


def iter_reports(
    client: FactsClient,
    settings: Settings,
    term: Term,
    grade_level: str | None = None,
    student_ids: set[int] | None = None,
    as_of: dt.date | None = None,
    skip: Callable[[StudentDemographics], bool] | None = None,
) -> Iterator[tuple[StudentDemographics, StudentReport | None, Exception | None]]:
    """Builds reports one student at a time, so the caller can write each
    PDF as soon as it exists instead of losing everything if student #400
    hits an error.

    Yields (student, report, error):
      * (student, report, None)  -- built fine
      * (student, None, error)   -- FACTS failed for this student only; the
                                    run carries on with the next one
      * (student, None, None)    -- skipped because skip(student) was true
    """
    as_of = as_of or dt.date.today()

    students = fetch_roster(
        client,
        settings.school_code,
        grade_level=grade_level,
        student_ids=student_ids,
    )
    logger.info("Roster matched %d active student(s)", len(students))

    ref = load_reference_data(client, settings.school_code)

    for i, student in enumerate(students, start=1):
        if skip and skip(student):
            logger.info("[%d/%d] Skipping student %s (PDF already exists)", i, len(students), student.student_id)
            yield student, None, None
            continue
        logger.info("[%d/%d] Building report for student %s", i, len(students), student.student_id)
        try:
            report = build_student_report(client, settings, ref, student, term, as_of)
        except FactsApiError as exc:
            logger.error("Student %s FAILED: %s", student.student_id, exc)
            yield student, None, exc
            continue
        yield student, report, None


def _safe_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    from dateutil import parser as dateparser
    try:
        return dateparser.parse(value).date()
    except (ValueError, TypeError):
        return None