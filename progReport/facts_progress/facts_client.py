"""Thin client for the FACTS SIS API.

Handles auth (Ocp-Apim-Subscription-Key header + api-version query param),
Sieve-style filter string building, and paging through the
`PagedResultOf...` envelope that every list endpoint in the FACTS API
returns (results / currentPage / pageCount / pageSize / rowCount).

Reference: FACTS SIS API OpenAPI spec (see project README).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterable, Iterator

import requests

from .config import Settings

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.5


class FactsApiError(RuntimeError):
    """Raised when the FACTS API returns an error response."""

    def __init__(self, status_code: int, message: str, url: str):
        super().__init__(f"FACTS API error {status_code} for {url}: {message}")
        self.status_code = status_code
        self.url = url


def sieve_and(*clauses: str | None) -> str:
    """Joins Sieve filter clauses with AND (comma), dropping empty ones.

    Example: sieve_and("gradeLevel==09", "status==Active") ->
             "gradeLevel==09,status==Active"
    """
    parts = [c for c in clauses if c]
    return ",".join(parts)


def sieve_in(field: str, values: Iterable[Any]) -> str:
    """Builds an OR clause for 'field equals one of values', Sieve-style:
    field==v1|field==v2|field==v3
    """
    values = list(values)
    if not values:
        return ""
    return "|".join(f"{field}=={v}" for v in values)


class FactsClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                # Header name is fixed by FACTS/Azure APIM as
                # "Ocp-Apim-Subscription-Key", but the value that
                # belongs here is your school-scoped API key, not your
                # developer subscription key -- see Settings.api_key.
                "Ocp-Apim-Subscription-Key": settings.api_key,
                "Accept": "application/json",
            }
        )

    def _request(self, method: str, path: str, params: dict | None = None, **kwargs) -> requests.Response:
        url = self.settings.base_url.rstrip("/") + path
        params = dict(params or {})
        params.setdefault("api-version", self.settings.api_version)

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.request(method, url, params=params, timeout=30, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("Request to %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(
                    "FACTS API returned %d for %s (attempt %d/%d); retrying",
                    resp.status_code, url, attempt, MAX_RETRIES,
                )
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue

            if not resp.ok:
                message = _extract_error_message(resp)
                if resp.status_code in (401, 403):
                    message += (
                        " (A 401/403 on every request usually means FACTS_API_KEY in .env is wrong -- "
                        "double check it's your school-scoped API key from the Developer Portal, not "
                        "your shorter developer subscription key.)"
                    )
                raise FactsApiError(resp.status_code, message, url)

            return resp

        if last_exc:
            raise FactsApiError(0, str(last_exc), url)
        raise FactsApiError(resp.status_code, _extract_error_message(resp), url)

    def get_paged(
        self,
        path: str,
        filters: str | None = None,
        sorts: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        extra_params: dict | None = None,
    ) -> Iterator[dict]:
        """Yields every result dict across all pages of a Sieve-filtered
        list endpoint.
        """
        page = 1
        while True:
            params = dict(extra_params or {})
            if filters:
                params["Filters"] = filters
            if sorts:
                params["Sorts"] = sorts
            params["Page"] = page
            params["PageSize"] = page_size

            resp = self._request("GET", path, params=params)
            payload = resp.json()
            results = payload.get("results") or []
            for row in results:
                yield row

            page_count = payload.get("pageCount") or 1
            if page >= page_count or not results:
                break
            page += 1

    def get_one(self, path: str, params: dict | None = None) -> dict:
        """GETs a single-resource endpoint (e.g. /People/{personId})."""
        resp = self._request("GET", path, params=params)
        return resp.json()


def _extract_error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:500]
    # FACTS error shapes seen in the spec: ErrorResponse / ProblemDetails
    for key in ("detail", "title", "message"):
        if body.get(key):
            return str(body[key])
    return str(body)[:500]
