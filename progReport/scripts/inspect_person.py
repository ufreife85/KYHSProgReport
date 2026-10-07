#!/usr/bin/env python3
"""Confirms how to get a student's name from /People, the way your working
AT Tracker script does it: a student's personId equals their studentId.

Two read-only checks, using the student id you give it:
  1. GET /People/{studentId}                      (one person)
  2. GET /People with Filters=personId==A|B|C     (several people in one call,
     which is how 505 students can be looked up in ~13 calls instead of 505)

Prints NO names or other personal data -- only yes/no answers, counts, and
any error text FACTS sends back.

Run: python scripts/inspect_person.py --student 1206150 --student 1201002
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient


def filled(value) -> bool:
    return bool(value.strip()) if isinstance(value, str) else False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check name lookup via /People using studentId as personId.")
    parser.add_argument("--student", type=int, action="append", required=True, metavar="STUDENT_ID",
                        help="repeat for more than one student")
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    ids = args.student

    print(f"== 1. GET /People/{ids[0]}  (studentId used as personId)")
    try:
        person = client.get_one(f"/People/{ids[0]}", params={})
        print(f"  OK. firstName filled: {filled(person.get('firstName'))}   "
              f"lastName filled: {filled(person.get('lastName'))}   "
              f"personId matches: {person.get('personId') == ids[0]}")
    except FactsApiError as exc:
        print(f"  FAILED -- {exc}")

    print(f"\n== 2. GET /People?Filters=personId=={'|'.join(str(i) for i in ids)}")
    try:
        payload = client.get_one("/People", params={
            "Filters": "personId==" + "|".join(str(i) for i in ids),
            "Page": 1, "PageSize": 200,
        })
        rows = payload.get("results", [])
        returned = {r.get("personId") for r in rows}
        print(f"  OK. rowCount={payload.get('rowCount')}, {len(rows)} row(s) returned")
        for sid in ids:
            row = next((r for r in rows if r.get("personId") == sid), None)
            if row is None:
                print(f"  id {sid}: not returned")
            else:
                print(f"  id {sid}: returned; firstName filled: {filled(row.get('firstName'))}   "
                      f"lastName filled: {filled(row.get('lastName'))}")
        extra = returned - set(ids)
        print(f"  rows returned that were NOT requested: {len(extra)}"
              f"{'  (the filter is NOT narrowing)' if extra else ''}")
    except FactsApiError as exc:
        print(f"  FAILED -- {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())