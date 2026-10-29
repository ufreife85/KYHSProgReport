"""Realistic sample FACTS API responses, keyed by request path, used by
the offline smoke test (scripts/smoke_test.py). Shapes match the
OpenAPI examples in the FACTS SIS API spec.
"""
from __future__ import annotations

SCHOOL_ID = 5001
SCHOOL_CODE = "MA"
TERM_ID = 2
YEAR_ID = 7

PRIOR_YEAR_ID = 6

TERMS = {
    "results": [
        {"termID": 1, "yearID": YEAR_ID, "name": "Full Year", "firstDay": "2026-08-25", "lastDay": "2027-06-15", "schoolCode": SCHOOL_CODE},
        {"termID": TERM_ID, "yearID": YEAR_ID, "name": "MP2 - Mid-Term", "firstDay": "2026-09-01", "lastDay": "2026-11-06", "schoolCode": SCHOOL_CODE},
        # FACTS term ids REPEAT every school year (every year has a "term 1").
        # This is last year's term with the SAME id as TERM_ID, to prove the
        # code never confuses the two.
        {"termID": TERM_ID, "yearID": PRIOR_YEAR_ID, "name": "MP2 - Mid-Term", "firstDay": "2025-09-01", "lastDay": "2025-11-06", "schoolCode": SCHOOL_CODE},
    ]
}

# /Students in real FACTS has NO names and NO homeroom -- just ids, status and
# grade. Current students have status "Enrolled" (not "Active").
STUDENTS = {
    "results": [
        {"school": {"status": "Enrolled", "gradeLevel": "09"}, "personStudentId": 2001, "studentId": 10321, "schoolCode": SCHOOL_CODE, "configSchoolId": SCHOOL_ID},
        {"school": {"status": "Enrolled", "gradeLevel": "09"}, "personStudentId": 2002, "studentId": 10455, "schoolCode": SCHOOL_CODE, "configSchoolId": SCHOOL_ID},
        {"school": {"status": "Enrolled", "gradeLevel": "10"}, "personStudentId": 2003, "studentId": 10500, "schoolCode": SCHOOL_CODE, "configSchoolId": SCHOOL_ID},
        {"school": {"status": "Withdrawn", "gradeLevel": "09"}, "personStudentId": 2099, "studentId": 10999, "schoolCode": SCHOOL_CODE, "configSchoolId": SCHOOL_ID},
        {"school": {"status": "Admissions", "gradeLevel": "09"}, "personStudentId": 2098, "studentId": 10888, "schoolCode": SCHOOL_CODE, "configSchoolId": SCHOOL_ID},
    ]
}

# /People: a student's personId is the SAME number as their studentId.
# (personStudentId would 404 -- see roster.py.)
PEOPLE = {
    10321: {"personId": 10321, "firstName": "Ari", "lastName": "Blumenthal"},
    10455: {"personId": 10455, "firstName": "Shira", "lastName": "Katz"},
    10500: {"personId": 10500, "firstName": "Dov", "lastName": "Levi"},
    10999: {"personId": 10999, "firstName": "Old", "lastName": "Student"},
    10888: {"personId": 10888, "firstName": "New", "lastName": "Applicant"},
}

# The batched /People list lookup "misses" these people; the code must then
# find them one at a time via /People/{id}.
PEOPLE_LIST_OMITS = {10455}

COURSES = {
    "results": [
        {"courseID": 801, "title": "Algebra I", "abbreviation": "ALG1", "schoolCode": SCHOOL_CODE, "levelID": 1, "attendance": True},
        {"courseID": 802, "title": "English 9", "abbreviation": "ENG9", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": True},
        {"courseID": 803, "title": "Chumash", "abbreviation": "CHUM", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": True},
        # Shacharit: attendance on, never graded.
        {"courseID": 805, "title": "Shacharit", "abbreviation": "SHAC", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": True},
        # Advising: attendance OFF -- must never appear on a report.
        {"courseID": 806, "title": "12th Grade Advisor", "abbreviation": "ADV", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": False},
        # Attendance on, but only meets in term 3 (not the report term).
        {"courseID": 807, "title": "Spring Elective", "abbreviation": "SPRE", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": True},
        # The level Ari was moved up to (his old "Chumash", course 803, stays on his record).
        {"courseID": 809, "title": "Chumash Honors", "abbreviation": "CHUH", "schoolCode": SCHOOL_CODE, "levelID": 1, "attendance": True},
        # An Activity (Robotics, sports): attendance is ON, but it is marked Activity -> never listed.
        {"courseID": 810, "title": "Robotics Team", "abbreviation": "ROBO", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": True, "activity": True},
        # Attendance OFF but the student has a grade in it -- must be left off
        # AND reported in omitted_with_grade.
        {"courseID": 808, "title": "Study Hall", "abbreviation": "STUD", "schoolCode": SCHOOL_CODE, "levelID": 2, "attendance": False},
    ]
}

# /People/Staff list (what load_reference_data reads) ...
STAFF = {
    301: {"staffId": 301, "firstName": "Sara", "lastName": "Goldberg", "name": "Goldberg, Sara"},
    302: {"staffId": 302, "firstName": "Moshe", "lastName": "Rubin", "name": "Rubin, Moshe"},
    303: {"staffId": 303, "firstName": "Dina", "lastName": "Katz", "name": "Katz, Dina"},
    304: {"staffId": 304, "firstName": "Yosef", "lastName": "Weiss", "name": "Weiss, Yosef"},
}
# ... which "misses" these people; the code must then find them one at a time
# via /People/Staff/{staffId}.
STAFF_LIST_OMITS = {304}

COURSE_LEVELS = {
    "results": [
        {"courseLevelID": 1, "levelName": "Honors"},
        {"courseLevelID": 2, "levelName": "Regular"},
    ]
}

# classId -> which student(s) it belongs to
def _terms(*meets: int) -> dict:
    """The termN flags FACTS puts on a class: True for each term it meets."""
    return {f"term{n}": (n in meets) for n in range(1, 7)}


# classId -> which student(s) it belongs to
CLASSES_BY_STUDENT = {
    10321: {
        "results": [
            # Two teachers: the primary and a secondary.
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 301, "secondaryStaffId": 302, **_terms(1, 2)},
            {"classId": 5002, "courseID": 802, "name": "English 9 - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 303, **_terms(1, 2)},
            # A class from LAST year -- the student's grade row for it has the
            # same bare termId as this year's term, and must NOT leak into
            # this year's report.
            {"classId": 4001, "courseID": 803, "name": "Chumash - Old", "section": "A", "yearId": PRIOR_YEAR_ID,
             "staffId": 302, **_terms(1, 2)},
            # No grade and NO attendance events at all -- must still appear
            # (with 0/0/0). Its teacher is missing from the staff list.
            {"classId": 5004, "courseID": 805, "name": "Shacharit - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 304, **_terms(1, 2)},
            # Attendance turned off for the course -> must not appear.
            {"classId": 5005, "courseID": 806, "name": "12th Grade Advisor - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 303, **_terms(1, 2)},
            # Enrolled, but only in term 3 (see ENROLLMENTS_BY_STUDENT): not part of
            # this term's report.
            {"classId": 5006, "courseID": 807, "name": "Spring Elective - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 301, **_terms(3)},
            # Ari moved from regular Chumash UP to Honors. The old class still
            # exists on his record WITH a grade and attendance, but he is no
            # longer enrolled in it -- it must not appear.
            {"classId": 5008, "courseID": 803, "name": "Chumash - GL", "section": "A", "yearId": YEAR_ID,
             "staffId": 302, **_terms(1, 2)},
            {"classId": 5009, "courseID": 809, "name": "Chumash Honors - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 302, **_terms(1, 2)},
            # Enrolled, attendance on, graded -- but an Activity: must not appear.
            {"classId": 5012, "courseID": 810, "name": "Robotics - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 303, **_terms(1, 2)},
        ]
    },
    10455: {
        "results": [
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 301, "secondaryStaffId": 302, **_terms(1, 2)},
            {"classId": 5003, "courseID": 803, "name": "Chumash - B", "section": "B", "yearId": YEAR_ID,
             "staffId": 302, **_terms(1, 2)},
            # No enrollment record in FACTS at all -> left off (and warned about).
            {"classId": 5011, "courseID": 802, "name": "English 9 - B", "section": "B", "yearId": YEAR_ID,
             "staffId": 303, **_terms(1, 2)},
            # Attendance off but graded -> left off, and listed as omitted.
            {"classId": 5007, "courseID": 808, "name": "Study Hall - A", "section": "A", "yearId": YEAR_ID,
             "staffId": 303, **_terms(1, 2)},
        ]
    },
}

GBK_SUMMARY_BY_STUDENT = {
    10321: {
        "results": [
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "88.4",
                "letterGrade": "B+",
                "fullAverage": 88.42,
            },
            {
                "classReference": {"classId": 5002},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "95.1",
                "letterGrade": "A",
                "fullAverage": 95.06,
            },
            # Sub-category rows (e.g. Homework, Tests) for the SAME class and
            # term, listed AFTER the overall row. A reader that just keeps the
            # last row per class would wrongly report these instead of 88.4.
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": 11},
                "termReference": {"termId": TERM_ID},
                "average": "100.0",
                "letterGrade": "A",
                "fullAverage": 100.0,
            },
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": 12},
                "termReference": {"termId": TERM_ID},
                "average": "61.5",
                "letterGrade": "D-",
                "fullAverage": 61.5,
            },
            # A full-year-average row for a different term should be ignored:
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": 1},
                "average": "90.0",
                "letterGrade": "A-",
                "fullAverage": 90.0,
            },
            {
                "classReference": {"classId": 5012},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "100.0",
                "letterGrade": "A",
                "fullAverage": 100.0,
            },
            # Ari's OLD Chumash class: graded, but he has since moved out of it.
            {
                "classReference": {"classId": 5008},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "80.0",
                "letterGrade": "B-",
                "fullAverage": 80.0,
            },
            # Last year's class, same bare termId as this year's term. A
            # term-id-only match would wrongly include it (see CLASSES_BY_STUDENT).
            {
                "classReference": {"classId": 4001},
                "studentReference": {"studentId": 10321},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "71.0",
                "letterGrade": "C-",
                "fullAverage": 71.0,
            },
        ]
    },
    10455: {
        "results": [
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10455},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "76.2",
                "letterGrade": "C+",
                "fullAverage": 76.19,
            },
            {
                "classReference": {"classId": 5003},
                "studentReference": {"studentId": 10455},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "",
                "letterGrade": "INC",
                "fullAverage": 0,
            },
            {
                "classReference": {"classId": 5007},
                "studentReference": {"studentId": 10455},
                "classCategoryReference": {"classCategoryId": -1},
                "termReference": {"termId": TERM_ID},
                "average": "99.0",
                "letterGrade": "A+",
                "fullAverage": 99.0,
            },
        ]
    },
}

ATTENDANCE_CODES = {
    "results": [
        {"code": "T", "name": "Tardy", "absent": False, "tardy": True, "excused": False},
        {"code": "A", "name": "Absent - Excused", "absent": True, "tardy": False, "excused": True},
        {"code": "U", "name": "Absent - Unexcused", "absent": True, "tardy": False, "excused": False},
        {"code": "C", "name": "Cut", "absent": True, "tardy": False, "excused": False},
        {"code": "P", "name": "Present", "absent": False, "tardy": False, "excused": False},
    ]
}

ATTENDANCE_BY_STUDENT = {
    10321: {
        "results": [
            {"attendanceId": 1, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5001}, "attendanceCode": "T", "attendanceDate": "2026-09-10"},
            {"attendanceId": 2, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5001}, "attendanceCode": "T", "attendanceDate": "2026-09-17"},
            {"attendanceId": 3, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5002}, "attendanceCode": "A", "attendanceDate": "2026-09-12"},
            {"attendanceId": 4, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5002}, "attendanceCode": "C", "attendanceDate": "2026-09-15"},
            {"attendanceId": 5, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5001}, "attendanceCode": "P", "attendanceDate": "2026-09-20"},
            {"attendanceId": 10, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5008}, "attendanceCode": "T", "attendanceDate": "2026-09-11"},
            # Outside the as-of window used by the smoke test -- should not be counted.
            {"attendanceId": 6, "studentReference": {"studentId": 10321}, "classReference": {"classId": 5001}, "attendanceCode": "T", "attendanceDate": "2026-12-01"},
        ]
    },
    10455: {
        "results": [
            {"attendanceId": 7, "studentReference": {"studentId": 10455}, "classReference": {"classId": 5003}, "attendanceCode": "C", "attendanceDate": "2026-09-05"},
            {"attendanceId": 8, "studentReference": {"studentId": 10455}, "classReference": {"classId": 5003}, "attendanceCode": "C", "attendanceDate": "2026-09-19"},
            {"attendanceId": 9, "studentReference": {"studentId": 10455}, "classReference": {"classId": 5001}, "attendanceCode": "T", "attendanceDate": "2026-09-08"},
        ]
    },
}

AS_OF_DATE = "2026-09-22"


def _enr(student_id: int, class_id: int, enrolled: bool, *terms: int) -> dict:
    """One FACTS enrollment record: `enrolled` plus enrolled1..enrolled6 (True for each term listed)."""
    row = {"studentId": student_id, "classId": class_id, "enrolled": enrolled, "gradeLevel": "09"}
    row.update({f"enrolled{n}": (n in terms) for n in range(1, 7)})
    return row


# /Academics/Enrollments, per student. Mirrors the FACTS "Hide Unenrolled" screen.
ENROLLMENTS_BY_STUDENT = {
    10321: {
        "results": [
            _enr(10321, 5001, True, 1, 2),
            _enr(10321, 5002, True, 1, 2),
            _enr(10321, 4001, True, 1, 2),          # last year's class (not this year's report anyway)
            _enr(10321, 5004, True, 1, 2),          # Shacharit: enrolled, never graded
            _enr(10321, 5005, True, 1, 2),          # Advisor: enrolled, but attendance is off
            _enr(10321, 5006, True, 3),             # enrolled only in term 3
            _enr(10321, 5008, False),               # moved OUT of regular Chumash
            _enr(10321, 5009, True, 1, 2),          # moved INTO Chumash Honors
            _enr(10321, 5012, True, 1, 2),          # Robotics: enrolled, but an Activity
        ]
    },
    10455: {
        "results": [
            _enr(10455, 5001, True, 1, 2),
            _enr(10455, 5003, True, 1, 2),
            _enr(10455, 5007, True, 1, 2),          # Study Hall: enrolled, attendance off, graded
            # (no record at all for class 5011)
        ]
    },
}