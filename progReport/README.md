# FACTS Mid-Term Progress Reports

Generates one PDF mid-term progress report per student, pulled live from
the FACTS SIS API: demographics, per-class gradebook (course, level,
numeric grade), and per-class attendance tallies (tardies, absences,
cuts).

## How it works

For each student in scope, the script:

1. Auto-detects (or is told) the current marking period/term.
2. Pulls the student's demographics, grade level, and homeroom (`/Students`).
3. Pulls every class the student is scheduled into (`/Classes/v2/Students/{id}`)
   and resolves each class's course name (`/Courses`) and course level
   (`/Gradebooks/CourseLevel`).
4. Pulls that term's numeric average per class (`/Gradebooks/GbkSummary`).
5. Pulls attendance events for the term-to-date (`/People/StudentAttendance`)
   and tallies tardies/absences/cuts per class, using the code mapping you
   set in `attendance_codes.json`.
6. Renders a PDF with reportlab.

## Setup (VS Code / Codespaces)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env with your real FACTS subscription key, api-version,
# school id, and school code
```

You'll need, from your FACTS Developer Portal app:

- **FACTS_SUBSCRIPTION_KEY** -- sent as the `Ocp-Apim-Subscription-Key`
  header on every request (this API does not use OAuth bearer tokens).
- **FACTS_API_VERSION** -- the `api-version` query string value FACTS
  expects. The OpenAPI spec doesn't publish a single default; check your
  developer portal docs or ask FACTS support if you're not sure.
- **FACTS_SCHOOL_ID** -- numeric school id (used to look up terms).
- **FACTS_SCHOOL_CODE** -- your school's short code (used to filter
  students/courses).

### Attendance codes

`attendance_codes.json` maps your FACTS attendance codes to the three
categories this report counts. It ships with placeholder codes
(`T` / `A` / `C`). Once your `.env` is filled in, run:

```bash
python main.py --list-attendance-codes
```

This prints every attendance code configured in your FACTS instance
(with its name and its absent/tardy/excused flags) so you can confirm
or edit the lists in `attendance_codes.json` to match exactly. A code
that isn't listed in any of the three arrays is simply not counted.

### Confirming your term setup

```bash
python main.py --list-terms
```

Prints every term FACTS has for your school. Useful for sanity-checking
that `--all` without `--term-id` will pick the marking period you
expect (it picks the *shortest* term whose date range contains today --
normally the actual progress-period, not the enclosing semester/year --
see `facts_progress/terms.py`).

## Usage

```bash
# Every active student in grade 9
python main.py --grade 09

# A single homeroom
python main.py --homeroom "Rm 204"

# The whole school
python main.py --all

# One or a few specific students (FACTS student ids)
python main.py --student 10321 --student 10455

# Pin to an explicit term instead of auto-detecting today's term
python main.py --all --term-id 42

# Tally attendance through a specific date instead of today
python main.py --all --as-of-date 2026-11-01

# Put your school's name in the PDF header
python main.py --all --school-name "Yeshivah Day School"

# See what's actually happening (raw API row counts, filters used, etc.)
python main.py --all -v
```

PDFs land in `output/` by default (one file per student,
`studentid_Lastname_Firstname.pdf` -- the id prefix makes files easy to
find individually and is what `google_apps_script/` matches on to email
each parent their child's report); override with `--output-dir`.

## Emailing reports to parents

See [`google_apps_script/README.md`](google_apps_script/README.md) for a
Google Sheets + Apps Script workflow: upload the `output/` PDFs to a
Drive folder, fill in a sheet of student id -> parent email(s), and run
a script from a custom Sheets menu to send each parent their child's
report as an attachment (with a dry-run/preview mode and duplicate-send
protection).

## Verifying it works without live API access

`scripts/smoke_test.py` runs the entire pipeline (roster -> gradebook ->
attendance -> PDF) against canned fixture data in
`facts_progress/tests/fixtures.py`, with no network calls and no real
credentials needed:

```bash
python scripts/smoke_test.py
```

It asserts the numbers come out right (grade averages, attendance
tallies, that a withdrawn student is excluded, that only the current
term's grade is used, etc.) and writes sample PDFs to
`output/smoke_test/` so you can preview the layout. Good first thing to
run after cloning, and good to re-run if you change any of the
aggregation logic.

## A note on Sieve filter syntax

Every FACTS list endpoint says it supports "Sieve filtering" but the
OpenAPI spec doesn't document the exact property paths for nested
fields (e.g. whether a student id filter is `studentId==123` or
`studentReference.studentId==123`). This project sends its best-guess
filters to keep API calls fast, but **always re-checks the relevant
id/date fields client-side** before using a row (see the comments at
the top of `gradebook.py` and `attendance.py`). So even if a guessed
filter turns out to be wrong for your instance, results stay correct --
just potentially slower, because more rows get downloaded and then
discarded client-side. Run with `-v` to see raw-vs-matched row counts
per student if you want to check.

## Project layout

```
main.py                        CLI entry point
attendance_codes.json          Your FACTS attendance code -> category mapping
.env.example                   Settings template (copy to .env)
facts_progress/
  config.py                    Settings + attendance code map loading
  facts_client.py              Auth, pagination, Sieve filter helpers
  models.py                    Plain dataclasses used across the app
  roster.py                    Student demographics / roster filtering
  terms.py                     Current-term resolution
  gradebook.py                 Course/level/numeric-grade lookup
  attendance.py                Attendance pull + tardy/absent/cut tallying
  aggregator.py                Ties the above into one StudentReport per student
  pdf_report.py                Renders the PDF with reportlab
  tests/
    fixtures.py                 Canned sample API responses
    fake_client.py               Serves fixtures in place of real HTTP calls
scripts/
  smoke_test.py                 Offline end-to-end check (see above)
```

## Extending

- **Branding**: `pdf_report.py` is plain reportlab/platypus -- add a
  logo with `reportlab.platypus.Image` above the title, or swap
  `HEADER_BG`/fonts for your school's colors.
- **More demographic fields**: `roster.py` currently reads name, grade
  level, and homeroom off `/Students`; the same response includes an
  `advisorId` and other fields from `/People/Demographic` if you want
  to add more to the header.
- **Advisor/teacher comments**: FACTS has `/Students/AdvisingNotes` and
  `/Gradebooks/TeacherClassNote` endpoints if you want to pull in
  narrative comments alongside the numeric data.
