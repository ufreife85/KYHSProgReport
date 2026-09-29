"""Realistic sample FACTS API responses, keyed by request path, used by
the offline smoke test (scripts/smoke_test.py). Shapes match the
OpenAPI examples in the FACTS SIS API spec.
"""
from __future__ import annotations

SCHOOL_ID = 5001
SCHOOL_CODE = "MA"
TERM_ID = 42
YEAR_ID = 7

TERMS = {
    "results": [
        {"termID": 41, "yearID": YEAR_ID, "name": "Full Year", "firstDay": "2026-08-25", "lastDay": "2027-06-15", "schoolCode": SCHOOL_CODE},
        {"termID": TERM_ID, "yearID": YEAR_ID, "name": "MP2 - Mid-Term", "firstDay": "2026-09-01", "lastDay": "2026-11-06", "schoolCode": SCHOOL_CODE},
    ]
}

STUDENTS = {
    "results": [
        {
            "school": {"status": "Active", "gradeLevel": "09"},
            "homeroom": "Rm 204",
            "studentId": 10321,
            "schoolCode": SCHOOL_CODE,
            "demographics": {"person": {"firstName": "Ari", "lastName": "Blumenthal", "personId": 55001}},
        },
        {
            "school": {"status": "Active", "gradeLevel": "09"},
            "homeroom": "Rm 204",
            "studentId": 10455,
            "schoolCode": SCHOOL_CODE,
            "demographics": {"person": {"firstName": "Shira", "lastName": "Katz", "personId": 55002}},
        },
        {
            "school": {"status": "Withdrawn", "gradeLevel": "09"},
            "homeroom": "Rm 204",
            "studentId": 10999,
            "schoolCode": SCHOOL_CODE,
            "demographics": {"person": {"firstName": "Old", "lastName": "Student", "personId": 55099}},
        },
    ]
}

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
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A"},
            {"classId": 5002, "courseID": 802, "name": "English 9 - A", "section": "A"},
        ]
    },
    10455: {
        "results": [
            {"classId": 5001, "courseID": 801, "name": "Algebra I - A", "section": "A"},
            {"classId": 5003, "courseID": 803, "name": "Chumash - B", "section": "B"},
        ]
    },
}

GBK_SUMMARY_BY_STUDENT = {
    10321: {
        "results": [
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "termReference": {"termId": TERM_ID},
                "average": "88.4",
                "letterGrade": "B+",
                "fullAverage": 88.42,
            },
            {
                "classReference": {"classId": 5002},
                "studentReference": {"studentId": 10321},
                "termReference": {"termId": TERM_ID},
                "average": "95.1",
                "letterGrade": "A",
                "fullAverage": 95.06,
            },
            # A full-year-average row for a different term should be ignored:
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10321},
                "termReference": {"termId": 41},
                "average": "90.0",
                "letterGrade": "A-",
                "fullAverage": 90.0,
            },
        ]
    },
    10455: {
        "results": [
            {
                "classReference": {"classId": 5001},
                "studentReference": {"studentId": 10455},
                "termReference": {"termId": TERM_ID},
                "average": "76.2",
                "letterGrade": "C+",
                "fullAverage": 76.19,
            },
            {
                "classReference": {"classId": 5003},
                "studentReference": {"studentId": 10455},
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
