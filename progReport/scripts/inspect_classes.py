#!/usr/bin/env python3
"""Read-only look at how ONE student's classes line up with the report, so we
can decide which classes belong on a Semester report and how to name the
teacher. Prints NO student or teacher names -- only class ids, course titles,
true/false flags, ids and counts.

Section A: for each of the student's classes in the report term's school year:
  - which terms it meets in (the class's term1..term6 flags),
  - the teacher / second teacher / aide ids on the class,
  - whether the student has an overall grade for it this term,
  - whether it has any counted attendance (tardy/absent/cut),
  - whether the report CURRENTLY shows it.
Section B: where a teacher's name can come from (the Staff record, and
  /People/{staffId} as a fallback) -- yes/no answers only.

Run: python scripts/inspect_classes.py --student 1206150
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.attendance import tally_attendance_for_student
from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from facts_progress.gradebook import (
    class_course_info, classes_in_year, fetch_grades_for_student,
    fetch_student_classes, load_reference_data,
)
from facts_progress.terms import get_current_term
from inspect_students import field_paths


def yn(flag) -> str:
    return "yes" if flag else "no"


def filled(value) -> bool:
    return bool(value.strip()) if isinstance(value, str) else False


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one student's classes vs the report.")
    parser.add_argument("--student", type=int, required=True, metavar="STUDENT_ID")
    args = parser.parse_args()
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    sid = args.student

    try:
        term = get_current_term(client, settings.school_id)
        print(f"Report term: term_id={term.term_id}, year_id={term.year_id} ({term.name})\n")
        ref = load_reference_data(client, settings.school_code)
        year_classes = classes_in_year(fetch_student_classes(client, sid), term.year_id)
        grades = fetch_grades_for_student(client, sid, term.term_id)
        today = dt.date.today()
        from dateutil import parser as dp
        start = dp.parse(term.first_day).date() if term.first_day else today
        end = min(today, dp.parse(term.last_day).date()) if term.last_day else today
        tallies = tally_attendance_for_student(client, settings.attendance_codes, sid, start, end)
    except FactsApiError as exc:
        print(f"FACTS error: {exc}")
        return 1

    print(f"== A. {len(year_classes)} class(es) in year {term.year_id} for student {sid}")
    print(f"   (term flags = which of term1..term6 the class meets in; this report is term {term.term_id})")
    staff_ids = set()
    for cid in sorted(year_classes):
        info = year_classes[cid]
        title, level = class_course_info(ref, info)
        flags = ",".join(str(n) for n, on in info["terms"].items() if on) or "none"
        has_grade = grades.get(cid) is not None
        has_grade_row = cid in grades
        has_att = cid in tallies
        shown_now = has_grade_row or has_att
        for k in ("staffId", "secondaryStaffId", "aideId"):
            if info.get(k):
                staff_ids.add(info[k])
        print(f"  class {cid}: '{title}' | meets terms: {flags} | staffId={info.get('staffId')} "
              f"second={info.get('secondaryStaffId')} aide={info.get('aideId')} | "
              f"overall-grade row: {yn(has_grade_row)} (has a number: {yn(has_grade)}) | "
              f"counted attendance: {yn(has_att)} | shown today: {yn(shown_now)}")

    print("\n== B. Where a teacher's name could come from")
    sample = sorted(i for i in {info.get("staffId") for info in year_classes.values()} if i)[:1]
    if not sample:
        print("  no class has a staffId, so no teacher lookup is possible from class data.")
        return 0
    staff_id = sample[0]
    print(f"  testing with staffId {staff_id}")
    for label, path in (("Staff record /People/Staff/{id}", f"/People/Staff/{staff_id}"),
                        ("Person record /People/{id} (staffId used as personId)", f"/People/{staff_id}")):
        try:
            rec = client.get_one(path, params={})
            print(f"  {label}: OK. fields: {', '.join(sorted(set(field_paths(rec))))}")
            person = (rec.get("demographics") or {}).get("person") or {}
            print(f"     firstName filled: {filled(rec.get('firstName'))}  lastName filled: {filled(rec.get('lastName'))}  "
                  f"name filled: {filled(rec.get('name'))}  demographics.person names filled: "
                  f"{filled(person.get('firstName')) and filled(person.get('lastName'))}")
        except FactsApiError as exc:
            print(f"  {label}: FAILED -- {exc}")

    print("  Staff list /People/Staff (page 1):")
    try:
        payload = client.get_one("/People/Staff", params={"Page": 1, "PageSize": 100})
        rows = payload.get("results", [])
        print(f"     rowCount={payload.get('rowCount')}, pageCount={payload.get('pageCount')}, {len(rows)} row(s) on page 1")
        if rows:
            r0 = rows[0]
            print(f"     firstName filled: {filled(r0.get('firstName'))}  lastName filled: {filled(r0.get('lastName'))}  "
                  f"name filled: {filled(r0.get('name'))}")
        listed = {r.get("staffId") for r in rows}
        print(f"     staffIds from this student's classes found on page 1: "
              f"{len(staff_ids & listed)} of {len(staff_ids)}")
    except FactsApiError as exc:
        print(f"     FAILED -- {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())