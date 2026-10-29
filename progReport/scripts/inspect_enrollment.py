#!/usr/bin/env python3
"""Read-only check: does FACTS tell us which classes a student is CURRENTLY
enrolled in, as opposed to classes they were scheduled into and later left?

Why: a student who moved from Grade Level to Accelerated to Honors still has
the old classes on record, and the report currently can't tell them apart.

For one student this reads /Classes/v2/Students/{id} (the same call the report
uses) and prints, for the school year you pick (default: the newest year the
student has classes in):
  1. every field name found on a class record, and which ones look like they
     could be about enrollment (drop / enrol / withdraw / date / status ...),
  2. for each class, only the fields whose value DIFFERS between classes --
     that is where a "dropped" or "enrolled" marker would show up.
It prints course/class names and field values from the class records only: no
student or parent names, no emails.

Run: python scripts/inspect_enrollment.py --student 1207466
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient

HINT = re.compile(r"drop|enrol|withdr|date|status|activ|added|remov|delet|schedul|start|end|begin|stop|leave|left|transfer", re.I)
# Fields that are different on every class by nature; not interesting to compare.
ALWAYS_DIFFERENT = {"classId", "name", "section", "courseID", "id"}


def flatten(record: dict, prefix: str = "") -> dict:
    """{'a': {'b': 1}} -> {'a.b': 1}. Lists are kept whole."""
    out = {}
    for key, value in record.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


def analyze(rows: list[dict], year_id: int | None = None) -> dict:
    """Pure function (no network): returns the pieces the report prints."""
    flat_all = [flatten(r) for r in rows]
    years = sorted({f.get("yearId") for f in flat_all if f.get("yearId") is not None})
    chosen = year_id if year_id is not None else (years[-1] if years else None)
    flat = [f for f in flat_all if f.get("yearId") == chosen] if chosen is not None else flat_all
    fields = sorted({k for f in flat_all for k in f})
    hinted = [k for k in fields if HINT.search(k)]
    varying = sorted(
        k for k in fields
        if k not in ALWAYS_DIFFERENT and len({repr(f.get(k)) for f in flat}) > 1
    )
    return {"years": years, "year": chosen, "classes": flat, "fields": fields, "hinted": hinted, "varying": varying}


def main() -> int:
    parser = argparse.ArgumentParser(description="Look for an 'enrolled / dropped' marker on a student's classes.")
    parser.add_argument("--student", type=int, required=True, metavar="STUDENT_ID")
    parser.add_argument("--year-id", type=int, help="school year id (default: newest year found)")
    args = parser.parse_args()

    try:
        client = FactsClient(Settings.load())
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    try:
        rows = list(client.get_paged(f"/Classes/v2/Students/{args.student}"))
    except FactsApiError as exc:
        print(f"FACTS error: {exc}")
        return 1

    a = analyze(rows, args.year_id)
    print(f"Class records returned: {len(rows)}   school years present: {a['years']}   using year: {a['year']}")
    print(f"Classes in that year: {len(a['classes'])}\n")

    print(f"== 1. All {len(a['fields'])} field names on a class record")
    print("  " + ", ".join(a["fields"]))
    print("\n  Names that look enrollment-related: " + (", ".join(a["hinted"]) or "(none)"))

    print("\n== 2. Fields whose value differs between this year's classes")
    print("  " + (", ".join(a["varying"]) or "(none -- every field except id/name is identical across classes)"))

    print("\n== 3. Each class, showing only those differing fields")
    for f in sorted(a["classes"], key=lambda x: str(x.get("name"))):
        shown = ", ".join(f"{k}={f.get(k)!r}" for k in a["varying"])
        print(f"  classId {f.get('classId')} | {f.get('name')} | {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())