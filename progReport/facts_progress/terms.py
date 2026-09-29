"""Resolves the school term/marking period a progress report should use."""
from __future__ import annotations

import datetime as dt
import logging

from dateutil import parser as dateparser

from .facts_client import FactsClient
from .models import Term

logger = logging.getLogger(__name__)


class NoActiveTermError(RuntimeError):
    pass


def _parse_date(value: str) -> dt.date:
    return dateparser.parse(value).date()


def get_all_terms(client: FactsClient, school_id: int) -> list[Term]:
    rows = client.get_paged(f"/SchoolTerms/v2/Schools/{school_id}")
    terms = []
    for row in rows:
        terms.append(
            Term(
                term_id=row["termID"],
                year_id=row["yearID"],
                name=row.get("name") or f"Term {row['termID']}",
                first_day=row.get("firstDay"),
                last_day=row.get("lastDay"),
            )
        )
    return terms


def get_current_term(client: FactsClient, school_id: int, as_of: dt.date | None = None) -> Term:
    """Returns the term whose [firstDay, lastDay] range contains `as_of`
    (default: today). If more than one term matches (e.g. a semester and
    a nested marking period both cover today), the shortest one wins,
    since that's normally the actual progress-report period rather than
    the enclosing semester/year.
    """
    as_of = as_of or dt.date.today()
    terms = get_all_terms(client, school_id)

    candidates = []
    for term in terms:
        if not term.first_day or not term.last_day:
            continue
        try:
            start = _parse_date(term.first_day)
            end = _parse_date(term.last_day)
        except (ValueError, TypeError):
            continue
        if start <= as_of <= end:
            candidates.append((end - start, term))

    if not candidates:
        raise NoActiveTermError(
            f"No FACTS term covers {as_of.isoformat()} for school {school_id}. "
            "Pass --term-id explicitly instead."
        )

    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def get_term_by_id(client: FactsClient, school_id: int, term_id: int) -> Term:
    for term in get_all_terms(client, school_id):
        if term.term_id == term_id:
            return term
    raise NoActiveTermError(f"Term id {term_id} not found for school {school_id}.")
