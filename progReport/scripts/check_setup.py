#!/usr/bin/env python3
"""Run this against your REAL .env credentials before generating a full
batch of reports. It checks the specific things that have caused the
most back-and-forth pain on past projects, so you catch them once here
instead of discovering them one PDF at a time:

  1. Auth / connectivity  -- is FACTS_API_KEY actually valid? (one cheap
     request, not a full pull)
  2. Attendance codes     -- does attendance_codes.json actually match
     every code your school uses in FACTS, or is something silently
     going uncounted?
  3. Term auto-detection  -- which term does "today" resolve to, and is
     that really the progress period (not the whole semester/year)?
  4. Sieve filters        -- for one real student, do the gradebook and
     attendance filters actually narrow anything, or are they fetching
     more/less than expected? (raw API rows vs. rows that survive the
     client-side id/date re-check)

This makes real API calls (it needs your live credentials) but never
writes any PDFs or touches attendance_codes.json -- it only reads and
reports.

Usage:
    python scripts/check_setup.py                    # checks 1-3 only
    python scripts/check_setup.py --student 10321     # checks 1-4
    python scripts/check_setup.py --student 10321 --term-id 42
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from facts_progress.attendance import fetch_attendance_codes, tally_attendance_for_student
from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from facts_progress.gradebook import fetch_grades_for_student, fetch_student_classes
from facts_progress.terms import NoActiveTermError, get_all_terms, get_current_term, get_term_by_id

logger = logging.getLogger("facts_progress")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanity-check your FACTS setup against the live API.")
    parser.add_argument(
        "--student", type=int, metavar="STUDENT_ID",
        help="A real, currently-active FACTS student id to run the check-4 Sieve-filter check against. "
             "Omit to skip check 4 (checks 1-3 don't need a student id).",
    )
    parser.add_argument("--term-id", type=int, help="Explicit term id for check 4 instead of auto-detecting today's term.")
    parser.add_argument("--as-of-date", type=str, help="Date (YYYY-MM-DD) for the attendance window in check 4. Defaults to today.")
    return parser.parse_args(argv)


def header(n: int, title: str) -> None:
    print(f"\n{'=' * 70}\n{n}. {title}\n{'=' * 70}")


def main(argv=None) -> int:
    args = parse_args(argv)
    # DEBUG so the existing raw-vs-matched instrumentation in
    # gradebook.py / attendance.py prints during check 4.
    logging.basicConfig(level=logging.DEBUG, format="  [%(name)s] %(message)s")

    try:
        settings = Settings.load()
    except ConfigError as exc:
        print(f"\nFAILED to load settings from .env:\n  {exc}")
        return 2

    client = FactsClient(settings)
    problems = 0

    # --- 1. Auth / connectivity -------------------------------------
    header(1, "Auth / connectivity")
    try:
        payload = client.get_one(
            "/Students",
            params={"Page": 1, "PageSize": 1, "Filters": f"schoolCode=={settings.school_code}"},
        )
        row_count = payload.get("rowCount")
        print(f"OK -- FACTS_API_KEY is valid. /Students reports {row_count} student(s) for school code "
              f"'{settings.school_code}'.")
        if row_count == 0:
            print("  NOTE: 0 students for that school code -- double check FACTS_SCHOOL_CODE in .env "
                  "(auth itself is fine, this would be a different setting).")
    except FactsApiError as exc:
        print(f"FAILED -- {exc}")
        print("\nStopping here: nothing else in this script can succeed until auth works.")
        return 1

    # --- 2. Attendance code reconciliation ----------------------------
    header(2, "Attendance codes")
    try:
        live_codes = fetch_attendance_codes(client)
    except FactsApiError as exc:
        print(f"FAILED to fetch /Academics/AttendanceCodes -- {exc}")
        problems += 1
        live_codes = {}

    if live_codes:
        configured = (
            settings.attendance_codes.tardy_codes
            | settings.attendance_codes.absent_codes
            | settings.attendance_codes.cut_codes
        )
        live_code_set = set(live_codes.keys())

        unmapped = sorted(live_code_set - configured)
        missing = sorted(configured - live_code_set)

        print(f"FACTS has {len(live_code_set)} attendance code(s) configured for your school.")
        if unmapped:
            problems += 1
            print(f"\n  ATTENTION -- {len(unmapped)} code(s) exist in FACTS but are NOT in "
                  f"attendance_codes.json (events using these will be silently ignored):")
            for code in unmapped:
                info = live_codes[code]
                print(f"    {code:<8} {info['name']:<30} absent={info['absent']} tardy={info['tardy']} excused={info['excused']}")
        if missing:
            problems += 1
            print(f"\n  ATTENTION -- {len(missing)} code(s) in attendance_codes.json don't exist in FACTS "
                  f"(likely a typo):")
            for code in missing:
                print(f"    {code}")
        if not unmapped and not missing:
            print("OK -- every code in attendance_codes.json matches a real FACTS code, and every FACTS "
                  "code is mapped (or intentionally left out).")

    # --- 3. Term auto-detection ---------------------------------------
    header(3, "Term auto-detection")
    try:
        all_terms = sorted(get_all_terms(client, settings.school_id), key=lambda t: (t.first_day or ""))
        current = get_current_term(client, settings.school_id)
        print(f"Today ({dt.date.today().isoformat()}) auto-resolves to:")
        print(f"  term_id={current.term_id}  \"{current.name}\"  {current.first_day} to {current.last_day}")
        print(f"\nAll {len(all_terms)} term(s) for this school (<-- marks the one auto-detected above):")
        for term in all_terms:
            marker = " <--" if term.term_id == current.term_id else ""
            print(f"  {term.term_id}\t{term.name}\t{term.first_day} to {term.last_day}\t(year {term.year_id}){marker}")
        print("\nDouble check: is the marked term the actual mid-term progress period, and not the "
              "enclosing semester/full year? If not, you'll need --term-id on main.py instead of relying "
              "on auto-detection.")
    except NoActiveTermError as exc:
        problems += 1
        print(f"FAILED -- {exc}")
        current = None
    except FactsApiError as exc:
        problems += 1
        print(f"FAILED to fetch terms -- {exc}")
        current = None

    # --- 4. Sieve filter verification (one real student) --------------
    header(4, "Sieve filter verification")
    if not args.student:
        print("SKIPPED -- pass --student <id> (a real, active FACTS student id) to run this check.")
    elif current is None and not args.term_id:
        print("SKIPPED -- term auto-detection failed above and no --term-id was given.")
    else:
        try:
            term = get_term_by_id(client, settings.school_id, args.term_id) if args.term_id else current
            as_of = dt.date.fromisoformat(args.as_of_date) if args.as_of_date else dt.date.today()

            print(f"Running for student {args.student}, term_id={term.term_id} (\"{term.name}\"), "
                  f"as_of={as_of.isoformat()}.")
            print("Watch for the [facts_progress.gradebook] / [facts_progress.attendance] DEBUG lines "
                  "below -- they show raw API rows fetched vs. rows that survived the client-side "
                  "id/date re-check. A huge gap (e.g. 500 raw, 2 matched) means the server-side Sieve "
                  "filter isn't narrowing anything on your instance -- still correct, just slower.\n")

            classes = fetch_student_classes(client, args.student)
            print(f"  -> {len(classes)} class(es) found for this student (any term).")

            grades = fetch_grades_for_student(client, args.student, term.term_id)
            print(f"  -> {len(grades)} class(es) with a matched grade row in term {term.term_id}.")

            term_start = _safe_date(term.first_day) or as_of
            term_end = min(as_of, _safe_date(term.last_day) or as_of)
            if term_end < term_start:
                term_end = term_start
            tallies = tally_attendance_for_student(client, settings.attendance_codes, args.student, term_start, term_end)
            print(f"  -> {len(tallies)} class(es) with tallied attendance between {term_start} and {term_end}.")

            if not classes:
                problems += 1
                print("\n  ATTENTION -- 0 classes found. Either this student id is wrong/inactive, or "
                      "/Classes/v2/Students/{id} isn't returning what's expected.")
        except FactsApiError as exc:
            problems += 1
            print(f"FAILED -- {exc}")

    # --- summary --------------------------------------------------------
    print(f"\n{'=' * 70}")
    if problems:
        print(f"{problems} thing(s) above need attention before running main.py on a full batch.")
    else:
        print("All checks that ran passed. Safe to run main.py on a small batch (e.g. one homeroom) next.")
    print("=" * 70)
    return 1 if problems else 0


def _safe_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    from dateutil import parser as dateparser
    try:
        return dateparser.parse(value).date()
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    sys.exit(main())
