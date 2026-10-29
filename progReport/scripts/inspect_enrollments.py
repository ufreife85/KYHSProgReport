#!/usr/bin/env python3
"""Read-only check of FACTS's class ENROLLMENT records for one student.

The FACTS API spec has GET /Academics/Enrollments (fields: studentId, classId,
enrolled, enrolled1..enrolled6, ...). In the FACTS screen that is the
"Hide Unenrolled" list, with a checkbox per class and per semester. This
script reads it for one student and prints, per class:

    class name | enrolled | enrolled1 .. enrolled6

so you can compare it to what the FACTS screen shows for that student.

It prints class names and true/false flags only -- no student or parent names.

Run: python scripts/inspect_enrollments.py --student 1207466
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient

FLAGS = ["enrolled"] + [f"enrolled{n}" for n in range(1, 7)]


def summarize(enrollments: list[dict], classes: dict[int, dict], student_id: int, year_id: int | None) -> dict:
    """Pure function (no network). Matches enrollment rows to the student's
    classes and returns what the script prints."""
    mine = [e for e in enrollments if e.get("studentId") == student_id]   # never trust the server filter alone
    by_class = {e.get("classId"): e for e in mine}
    in_year = {cid: c for cid, c in classes.items() if year_id is None or c.get("yearId") == year_id}
    rows, no_record = [], []
    for cid, c in in_year.items():
        e = by_class.get(cid)
        if e is None:
            no_record.append(c.get("name"))
        else:
            rows.append((str(c.get("name")), cid, {k: e.get(k) for k in FLAGS}))
    rows.sort()
    extra = [cid for cid in by_class if cid not in in_year]
    return {"total_rows": len(enrollments), "mine": len(mine), "rows": rows, "no_record": no_record, "other_classes": len(extra)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a student's class enrollment flags.")
    parser.add_argument("--student", type=int, required=True, metavar="STUDENT_ID")
    parser.add_argument("--year-id", type=int, help="school year id (default: newest year the student has classes in)")
    args = parser.parse_args()

    try:
        client = FactsClient(Settings.load())
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2

    try:
        class_rows = list(client.get_paged(f"/Classes/v2/Students/{args.student}"))
        enrollments = list(client.get_paged("/Academics/Enrollments", filters=f"studentId=={args.student}", page_size=1000))
    except FactsApiError as exc:
        print(f"FACTS error: {exc}")
        return 1

    classes = {r["classId"]: {"name": r.get("name"), "yearId": r.get("yearId")} for r in class_rows if r.get("classId") is not None}
    year_id = args.year_id or max((c["yearId"] for c in classes.values() if c["yearId"] is not None), default=None)
    out = summarize(enrollments, classes, args.student, year_id)

    print(f"Enrollment rows returned: {out['total_rows']}  (for this student: {out['mine']})   using school year: {year_id}")
    if out["total_rows"] and out["mine"] != out["total_rows"]:
        print("  NOTE: the server filter did not narrow to this student; rows for other students were ignored.")
    print(f"Enrollment rows for classes outside that year: {out['other_classes']}")
    print(f"Classes this year with NO enrollment record: {len(out['no_record'])}"
          + (" -> " + ", ".join(map(str, out["no_record"])) if out["no_record"] else ""))
    print("\nclass | " + " ".join(f"{k:>9}" for k in FLAGS))
    for name, cid, flags in out["rows"]:
        print(f"{name} (class {cid}) | " + " ".join(f"{str(flags[k]):>9}" for k in FLAGS))
    return 0


if __name__ == "__main__":
    sys.exit(main())