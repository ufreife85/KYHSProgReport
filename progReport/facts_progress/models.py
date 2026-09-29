"""Plain dataclasses for the data we assemble per student. Kept separate
from the raw FACTS API response shapes so the PDF builder and CLI don't
need to know anything about the API.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StudentDemographics:
    student_id: int
    person_id: int | None
    first_name: str
    last_name: str
    grade_level: str
    homeroom: str
    advisor_name: str | None = None


@dataclass
class Term:
    term_id: int
    year_id: int
    name: str
    first_day: str
    last_day: str


@dataclass
class ClassProgress:
    """One row of the report: a single class with its numeric grade and
    attendance tallies for the term-to-date."""
    class_id: int
    course_name: str
    course_level: str
    numeric_grade: float | None
    tardies: int = 0
    absences: int = 0
    cuts: int = 0


@dataclass
class StudentReport:
    student: StudentDemographics
    term: Term
    classes: list[ClassProgress] = field(default_factory=list)
