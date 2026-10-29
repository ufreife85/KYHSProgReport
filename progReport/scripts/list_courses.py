#!/usr/bin/env python3
"""Read-only: lists every course in FACTS by whether it has ATTENDANCE turned on.

The progress report only includes courses with attendance enabled (and only
the ones the student is enrolled in). This shows exactly which courses that
covers, so you can eyeball it against your course list and catch anything that
would print but shouldn't (or the reverse).

  ACTIVITY -> marked "Activity" in FACTS (Robotics, sports teams...); never appears,
              even if it takes attendance
  ON       -> attendance on, not an activity: can appear on a report
  OFF      -> attendance off; never appears
  UNKNOWN  -> FACTS sent no attendance value; the report KEEPS these

Course titles only -- no student or staff information. One FACTS request.

Run: python scripts/list_courses.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient


def group_courses(rows: list[dict], school_code: str) -> dict[str, list[str]]:
    """Pure function: {'activity','on','off','unknown'} -> sorted trimmed course titles."""
    out: dict[str, set[str]] = {"activity": set(), "on": set(), "off": set(), "unknown": set()}
    for row in rows:
        if (row.get("schoolCode") or "").strip().lower() != school_code.strip().lower():
            continue
        title = (row.get("title") or row.get("abbreviation") or f"Course {row.get('courseID')}").strip()
        flag = row.get("attendance")
        if row.get("activity") is True:
            out["activity"].add(title)
        else:
            out["on" if flag is True else "off" if flag is False else "unknown"].add(title)
    return {k: sorted(v, key=str.lower) for k, v in out.items()}


def main() -> int:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    client = FactsClient(settings)
    try:
        rows = list(client.get_paged("/Courses", filters=f"schoolCode=={settings.school_code}"))
    except FactsApiError as exc:
        print(f"FACTS error: {exc}")
        return 1

    groups = group_courses(rows, settings.school_code)
    print(f"{len(rows)} course records.  ACTIVITY: {len(groups['activity'])}   ON: {len(groups['on'])}   "
          f"OFF: {len(groups['off'])}   UNKNOWN: {len(groups['unknown'])}  (distinct titles)\n")
    labels = {"activity": "MARKED AS ACTIVITY -- never appears",
              "on": "ATTENDANCE ON -- can appear on a report", "off": "ATTENDANCE OFF -- never appears",
              "unknown": "FLAG MISSING -- kept on reports"}
    for key in ("activity", "on", "off", "unknown"):
        print(f"== {labels[key]} ({len(groups[key])})")
        for title in groups[key]:
            print(f"  {title}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())