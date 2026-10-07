#!/usr/bin/env python3
"""CLI entry point for generating FACTS mid-term progress report PDFs.

Examples:
    # Generate for every active student in grade 9
    python main.py --grade 09

    # Generate for every active student in the school
    python main.py --all

    # Generate for one or a few specific students (FACTS student ids)
    python main.py --student 10321 --student 10455

    # Use an explicit term instead of auto-detecting today's term
    python main.py --all --term-id 1 --year-id 271

    # Just see what attendance codes / terms your FACTS instance has
    python main.py --list-attendance-codes
    python main.py --list-terms
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

from facts_progress.aggregator import iter_reports
from facts_progress.attendance import fetch_attendance_codes
from facts_progress.config import ConfigError, Settings
from facts_progress.facts_client import FactsApiError, FactsClient
from facts_progress.pdf_report import build_student_pdf, student_filename
from facts_progress.terms import NoActiveTermError, get_all_terms, get_current_term, get_term_by_id

logger = logging.getLogger("facts_progress")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate FACTS mid-term progress report PDFs.")

    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all", action="store_true", help="Every active student in the school.")
    scope.add_argument("--grade", metavar="LEVEL", help="Only students in this grade level (e.g. 09).")
    scope.add_argument(
        "--student", action="append", type=int, metavar="STUDENT_ID",
        help="Only this student (FACTS student id). Repeat for multiple students.",
    )

    parser.add_argument("--term-id", type=int, help="Explicit FACTS term id instead of auto-detecting today's term. Term ids repeat every school year, so this needs --year-id too.")
    parser.add_argument("--year-id", type=int, help="School year id the --term-id belongs to (see --list-terms; e.g. 271 for 2026-27).")
    parser.add_argument(
        "--as-of-date", type=str,
        help="Date (YYYY-MM-DD) attendance is tallied through. Defaults to today. Grades always reflect FACTS's current data for the term.",
    )
    parser.add_argument("--school-name", default="Progress Report", help="Header text on the PDF (e.g. your school's name).")
    parser.add_argument("--output-dir", type=Path, help="Where to write PDFs. Defaults to ./output.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging (shows raw API row counts, filter strings used, etc.).")

    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip any student whose PDF is already in the output folder. Lets you re-run after a failure "
             "and only redo what's missing.",
    )
    parser.add_argument("--list-terms", action="store_true", help="Print all FACTS terms for the configured school and exit.")
    parser.add_argument(
        "--list-attendance-codes", action="store_true",
        help="Print all FACTS attendance codes for reference and exit (use this to fill in attendance_codes.json).",
    )

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = Settings.load()
    except ConfigError as exc:
        logger.error(str(exc))
        return 2

    client = FactsClient(settings)

    try:
        if args.list_attendance_codes:
            return _list_attendance_codes(client)
        if args.list_terms:
            return _list_terms(client, settings.school_id)

        term = _resolve_term(client, settings, args)
        as_of = _resolve_as_of_date(args)

        student_ids = set(args.student) if args.student else None
        output_dir = args.output_dir or (Path(__file__).resolve().parent / "output")
        output_dir.mkdir(parents=True, exist_ok=True)

        skip = (lambda s: (output_dir / student_filename(s)).exists()) if args.skip_existing else None

        written = skipped = 0
        failed: list[int] = []
        for student, report, error in iter_reports(
            client,
            settings,
            term=term,
            grade_level=args.grade,
            student_ids=student_ids,
            as_of=as_of,
            skip=skip,
        ):
            if error is not None:
                failed.append(student.student_id)
            elif report is None:
                skipped += 1
            else:
                path = output_dir / student_filename(student)
                build_student_pdf(report, args.school_name, path)
                written += 1
                logger.info("Wrote %s", path.name)
    except (FactsApiError, NoActiveTermError, ConfigError) as exc:
        logger.error(str(exc))
        return 1

    if not (written or skipped or failed):
        logger.warning("No students matched the given filters -- nothing to generate.")
        return 0

    logger.info("Done. %d PDF(s) written, %d skipped (already existed), %d failed. %d FACTS requests used. Folder: %s",
                written, skipped, len(failed), client.request_count, output_dir)
    if failed:
        logger.error("Failed student ids: %s -- re-run the same command with --skip-existing to retry only these.",
                     ", ".join(str(i) for i in failed))
        return 1
    return 0


def _resolve_term(client: FactsClient, settings: Settings, args: argparse.Namespace):
    if args.year_id and not args.term_id:
        logger.error("--year-id only makes sense together with --term-id.")
        raise SystemExit(2)
    if args.term_id:
        return get_term_by_id(client, settings.school_id, args.term_id, args.year_id)
    return get_current_term(client, settings.school_id)


def _resolve_as_of_date(args: argparse.Namespace) -> dt.date:
    if not args.as_of_date:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(args.as_of_date)
    except ValueError:
        logger.error("--as-of-date must be YYYY-MM-DD, got %r", args.as_of_date)
        raise SystemExit(2)


def _list_terms(client: FactsClient, school_id: int) -> int:
    for term in sorted(get_all_terms(client, school_id), key=lambda t: (t.first_day or "")):
        print(f"{term.term_id}\t{term.name}\t{term.first_day} to {term.last_day}\t(year {term.year_id})")
    return 0


def _list_attendance_codes(client: FactsClient) -> int:
    codes = fetch_attendance_codes(client)
    print(f"{'code':<10}{'name':<30}{'absent':<8}{'tardy':<8}{'excused':<8}")
    for code, info in sorted(codes.items()):
        print(f"{code:<10}{info['name']:<30}{str(info['absent']):<8}{str(info['tardy']):<8}{str(info['excused']):<8}")
    print("\nEdit attendance_codes.json so tardy_codes/absent_codes/cut_codes match the codes above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())