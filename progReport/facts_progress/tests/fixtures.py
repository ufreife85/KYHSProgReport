"""Realistic sample FACTS API responses, keyed by request path, used by
the offline smoke test (scripts/smoke_test.py). Shapes match the
OpenAPI examples in the FACTS SIS API spec.
"""
from __future__ import annotations

SCHOOL_ID = 5001
SCHOOL_CODE = "MA"
TERM_ID = 42
YEAR_ID = 7

PRIOR_YEAR_ID = 6

TERMS = {
    "results": [
        {"termID": 41, "yearID": YEAR_ID, "name": "Full Year", "firstDay": "2026-08-25", "lastDay": "2027-06-15", "schoolCode": SCHOOL_CODE},
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
        {"courseID": 801, "title": "Algebra I", "abbreviation": "ALG1", "schoolCode": SCHOOL_CODE, "levelID": 1},
        {"courseID": 802, "title": "English 9", "abbreviation": "ENG9", "schoolCode": SCHOOL_CODE, "levelID": 2},
        {"courseID": 803, "title": "Chumash", "abbreviation": "CHUM", "schoolCode": SCHOOL_CODE, "levelID": 2},
    ]
}

COURSE_LEVELS = {
    "results": [
        {"courseLevelID": 1, "levelName": "Honors"},
        {"courseLevelID": 2, "levelName": "Regular"},
    ]
}

# classId -> which student(s) it belongs to
CLASSES_BY_STUDENT = {
    10321: {
        "results": [
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A", "yearId": YEAR_ID},
            {"classId": 5002, "courseID": 802, "name": "English 9 - A", "section": "A", "yearId": YEAR_ID},
            # A class from LAST year -- the student's grade row for it has the
            # same bare termId as this year's term, and must NOT leak into
            # this year's report.
            {"classId": 4001, "courseID": 803, "name": "Chumash - Old", "section": "A", "yearId": PRIOR_YEAR_ID},
        ]
    },
    10455: {
        "results": [
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A", "yearId": YEAR_ID},
            {"classId": 5003, "courseID": 803, "name": "Chumash - B", "section": "B", "yearId": YEAR_ID},
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
                "termReference": {"termId": 41},
                "average": "90.0",
                "letterGrade": "A-",
                "fullAverage": 90.0,
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