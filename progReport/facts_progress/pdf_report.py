"""Builds one progress-report PDF per student using reportlab. One table:
Course, Level, Numeric Grade, Tardies, Absences, Cuts.
"""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import StudentReport

_styles = getSampleStyleSheet()
_TITLE = ParagraphStyle("ReportTitle", parent=_styles["Title"], fontSize=16, spaceAfter=2)
_SUBTITLE = ParagraphStyle("ReportSubtitle", parent=_styles["Normal"], fontSize=11, textColor=colors.HexColor("#444444"))
_FOOTER = ParagraphStyle("Footer", parent=_styles["Normal"], fontSize=8, textColor=colors.HexColor("#777777"))

HEADER_BG = colors.HexColor("#2E4057")
ROW_ALT_BG = colors.HexColor("#F2F4F7")
GRID_COLOR = colors.HexColor("#CCCCCC")


def _safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_\- ]+", "", text).strip()
    return re.sub(r"\s+", "_", text) or "student"


def output_filename(report: StudentReport) -> str:
    """studentId_lastName_firstName.pdf -- the student id prefix makes
    each file easy to look up individually and lets the email-to-parents
    script (see google_apps_script/) match a PDF to a student id
    unambiguously, even if two students share a name.
    """
    return student_filename(report.student)


def student_filename(s) -> str:
    return f"{s.student_id}_{_safe_filename(s.last_name)}_{_safe_filename(s.first_name)}.pdf"


def _report_table(report: StudentReport) -> Table:
    header = ["Course Name", "Course Level", "Numeric Grade", "Tardies", "Absences", "Cuts"]
    rows = [header]
    for c in report.classes:
        numeric = f"{c.numeric_grade:.1f}" if c.numeric_grade is not None else "—"
        rows.append([c.course_name, c.course_level or "—", numeric, str(c.tardies), str(c.absences), str(c.cuts)])
    if len(rows) == 1:
        rows.append(["No classes with grades or attendance recorded for this term.", "", "", "", "", ""])

    col_widths = [2.6 * inch, 1.2 * inch, 1.1 * inch, 0.75 * inch, 0.85 * inch, 0.6 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_table_style(len(rows)))
    return table


def _table_style(num_rows: int) -> TableStyle:
    style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]
    )
    for row in range(1, num_rows):
        if row % 2 == 0:
            style.add("BACKGROUND", (0, row), (-1, row), ROW_ALT_BG)
    return style


def build_student_pdf(report: StudentReport, school_name: str, output_path: Path) -> Path:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        title=f"Progress Report - {report.student.first_name} {report.student.last_name}",
    )

    story = []
    story.append(Paragraph(school_name, _TITLE))
    story.append(Paragraph(f"Mid-Term Progress Report &mdash; {report.term.name}", _SUBTITLE))
    story.append(Spacer(1, 14))

    s = report.student
    meta_rows = [
        ["Student:", f"{s.first_name} {s.last_name}", "Grade Level:", s.grade_level or "—"],
        ["Term Dates:", f"{report.term.first_day or '?'} – {report.term.last_day or '?'}", "", ""],
    ]
    meta_table = Table(meta_rows, colWidths=[1.0 * inch, 2.6 * inch, 1.1 * inch, 2.1 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 16))

    story.append(_report_table(report))

    story.append(Spacer(1, 24))
    story.append(
        Paragraph(
            "Generated from FACTS SIS data. This is an informational mid-term progress report, "
            "not an official report card.",
            _FOOTER,
        )
    )

    doc.build(story)
    return output_path