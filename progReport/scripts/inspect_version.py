#!/usr/bin/env python3
"""Checks ONE thing: does asking FACTS for a newer api-version make /Students
return student names?

Why: your FACTS SIS API definition file lists several versions of the Student
record. The oldest one (what api-version=1 gives you) has no names. The newest
one (V1_3) has `demographics.person.firstName / lastName`, `homeroom`, etc.

For one student this asks /Students again with api-version 1.1, 1.2 and 1.3
(with and without includes=demographics) and prints, for each try, only:
  - whether the request worked (or FACTS's error text),
  - which field names are NEW compared to what you get today,
  - yes/no: are firstName and lastName present and filled in.
It prints NO names or other personal data.

Run: python scripts/inspect_version.py --student 1206150
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from inspect_students import field_paths  # same folder

VERSIONS = ["1.1", "1.2", "1.3"]
INCLUDES = [None, "demographics"]


def fetch(client, sid, version, includes):
    params = {"Filters": f"studentId=={sid}", "Page": 1, "PageSize": 5, "api-version": version}
    if includes:
        params["includes"] = includes
    try:
        payload = client.get_one("/Students", params=params)
    except FactsApiError as exc:
        return None, str(exc)
    rows = [r for r in payload.get("results", []) if r.get("studentId") == sid]
    return (rows[0] if rows else {}), None


def filled(value) -> bool:
    return bool((value or "").strip()) if isinstance(value, str) else False


def main() -> int:
    parser = argparse.ArgumentParser(description="Does a newer api-version return student names?")
    parser.add_argument("--student", type=int, required=True, metavar="STUDENT_ID")
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    sid = args.student

    base, err = fetch(client, sid, settings.api_version, None)
    if err or not base:
        print(f"Could not read the student with your current api-version: {err or 'no row returned'}")
        return 1
    baseline = set(field_paths(base))
    print(f"Today (api-version={settings.api_version}): {len(baseline)} fields, no names.\n")

    for version in VERSIONS:
        for includes in INCLUDES:
            label = f"api-version={version}" + (f", includes={includes}" if includes else "")
            row, err = fetch(client, sid, version, includes)
            if err:
                print(f"{label}: FAILED -- {err}\n")
                continue
            if not row:
                print(f"{label}: worked but returned no row for this student\n")
                continue
            new = sorted(set(field_paths(row)) - baseline)
            person = (row.get("demographics") or {}).get("person") or {}
            print(f"{label}: OK")
            print(f"  new fields: {', '.join(new) or '(none)'}")
            print(f"  firstName filled: {filled(person.get('firstName'))}   "
                  f"lastName filled: {filled(person.get('lastName'))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())