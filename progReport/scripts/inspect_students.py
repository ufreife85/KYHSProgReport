#!/usr/bin/env python3
"""Read-only look at what your FACTS /Students records ACTUALLY contain, so
the roster code can be checked against real data instead of the OpenAPI
spec's examples. Prints NO names or other personal data -- only:

  1. every distinct student status value, how many students have it, and
     one example studentId for each (handy for picking a test student), and
  2. every field that appears in the records, and how many records have it
     (so we can see, e.g., whether names / homeroom are really in there).

Run: python scripts/inspect_students.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient


def field_paths(obj, prefix=""):
    """Yields the dotted path of every field in a JSON-like value
    (list items are shown with [] after the list's name)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from field_paths(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, list):
        yield prefix + "[]"
        if obj:
            yield from field_paths(obj[0], prefix + "[]")
    else:
        yield prefix


def inspect(client, school_code: str) -> None:
    statuses: Counter = Counter()
    example_id: dict = {}
    fields: Counter = Counter()
    total = 0

    for row in client.get_paged("/Students", filters=f"schoolCode=={school_code}"):
        total += 1
        status = (row.get("school") or {}).get("status")
        statuses[status] += 1
        example_id.setdefault(status, row.get("studentId"))
        for path in set(field_paths(row)):
            fields[path] += 1

    print(f"Read {total} student record(s) for school code '{school_code}'.\n")

    print("Student status values (status / how many students / example studentId):")
    for status, count in statuses.most_common():
        print(f"  {status!r:<20} {count:>6}   e.g. {example_id[status]}")

    print("\nFields found in the records (field / how many of the records have it):")
    for path, count in sorted(fields.items()):
        print(f"  {path:<45} {count:>6}")


def main() -> int:
    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"Could not load settings from .env: {exc}")
        return 2
    try:
        inspect(FactsClient(settings), settings.school_code)
    except FactsApiError as exc:
        print(f"FACTS API error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())