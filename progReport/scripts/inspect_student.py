#!/usr/bin/env python3
"""Probes how to get ONE student's name / grade level / homeroom out of the
real FACTS API. The /Students records don't include names or homeroom by
default, so this tries the options the OpenAPI spec hints at and reports
which ones work. Prints NO names or other personal data -- only field
names, counts, yes/no answers, and any error text FACTS sends back.

Run: python scripts/inspect_student.py --student 1206150
(use any studentId whose status is 'Enrolled' -- inspect_students.py lists examples)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from inspect_students import field_paths  # same folder: scripts/inspect_students.py

INCLUDES_CANDIDATES = ["demographics", "Demographics", "demographics.person", "person"]


def try_get(client, path, params):
    """Returns (payload, None) on success or (None, error_text)."""
    try:
        return client.get_one(path, params=params), None
    except FactsApiError as exc:
        return None, str(exc)


def paths_of(record) -> set:
    return set(field_paths(record))


def find_student_record(client, student_id):
    """Returns (record, how) -- tries a server-side filter first, then
    falls back to reading every page until the student turns up."""
    payload, err = try_get(client, "/Students", {"Filters": f"studentId=={student_id}", "Page": 1, "PageSize": 5})
    if payload is not None:
        hits = [r for r in payload.get("results", []) if r.get("studentId") == student_id]
        print(f"  server-side filter 'studentId=={student_id}': rowCount={payload.get('rowCount')}, "
              f"{len(payload.get('results', []))} row(s) returned, {len(hits)} actually this student")
        if len(hits) == 1 and payload.get("rowCount") == 1:
            return hits[0], "filter"
    else:
        print(f"  server-side filter 'studentId=={student_id}': FAILED -- {err}")
    print("  (filter didn't isolate the student -- reading pages until found; slower)")
    for row in client.get_paged("/Students"):
        if row.get("studentId") == student_id:
            return row, "scan"
    return None, "not found"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe how to get one student's name/homeroom from FACTS.")
    parser.add_argument("--student", type=int, required=True, metavar="STUDENT_ID")
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    sid = args.student

    print(f"== A. Finding student {sid} in /Students")
    record, how = find_student_record(client, sid)
    if record is None:
        print("  Student not found. Check the studentId.")
        return 1
    baseline = paths_of(record)
    print(f"  found via {how}. status = {(record.get('school') or {}).get('status')!r}")
    print("  fields in the plain record:", ", ".join(sorted(baseline)))
    person_id = record.get("personStudentId")

    print("\n== B. Does the 'includes' parameter on /Students add names (demographics)?")
    use_filter = how == "filter"
    for candidate in INCLUDES_CANDIDATES:
        params = {"includes": candidate, "Page": 1, "PageSize": 5}
        if use_filter:
            params["Filters"] = f"studentId=={sid}"
        payload, err = try_get(client, "/Students", params)
        if payload is None:
            print(f"  includes={candidate!r}: FAILED -- {err}")
            continue
        rows = [r for r in payload.get("results", []) if r.get("studentId") == sid] if use_filter else payload.get("results", [])
        new_fields = set()
        for r in rows:
            new_fields |= paths_of(r) - baseline
        print(f"  includes={candidate!r}: OK, {len(rows)} row(s) checked. NEW fields vs plain record: "
              f"{', '.join(sorted(new_fields)) or '(none)'}")

    print(f"\n== C. /People/{{personId}} using personStudentId={person_id} (alternative source for names)")
    payload, err = try_get(client, f"/People/{person_id}", {})
    if payload is None:
        print(f"  FAILED -- {err}")
    else:
        print("  fields:", ", ".join(sorted(paths_of(payload))))
        print(f"  firstName filled in: {bool((payload.get('firstName') or '').strip())}   "
              f"lastName filled in: {bool((payload.get('lastName') or '').strip())}   "
              f"personId matches personStudentId: {payload.get('personId') == person_id}")

    print("\n== D. /People/StudentsHomeroom (homeroom lookup)")
    payload, err = try_get(client, "/People/StudentsHomeroom",
                           {"Filters": f"studentId=={sid}", "Page": 1, "PageSize": 10})
    if payload is None:
        print(f"  FAILED -- {err}")
    else:
        rows = payload.get("results", [])
        mine = [r for r in rows if (r.get("studentReference") or {}).get("studentId") == sid]
        print(f"  rowCount={payload.get('rowCount')}, {len(rows)} row(s) returned, {len(mine)} actually this student")
        if mine:
            print("  fields:", ", ".join(sorted(paths_of(mine[0]))))
            print(f"  homeRoom filled in: {bool((mine[0].get('homeRoom') or '').strip())}")
            print(f"  (this student has {len(mine)} homeroom row(s) -- one per year/class?)")
    return 0


if __name__ == "__main__":
    sys.exit(main())