"""Thin client for the FACTS SIS API.

Handles auth (TWO required headers -- Ocp-Apim-Subscription-Key and
Facts-Api-Key, see FactsClient.__init__ -- plus the api-version query
param), Sieve-style filter string building, and paging through the
`PagedResultOf...` envelope that every list endpoint in the FACTS API
returns (results / currentPage / pageCount / pageSize / rowCount).

Reference: FACTS SIS API OpenAPI spec (see project README).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Iterable, Iterator

import requests

from .config import Settings

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
MAX_RETRIES = 6
RETRY_BACKOFF_SECONDS = 1.5
MAX_RETRY_WAIT_SECONDS = 60

# The FACTS plan's limits (Settings.rate_limit_per_second / _per_minute,
# currently 10/second and 100/minute) are per subscription, so anything else
# using the same keys (the Eligibility dashboard, the AT tracker) shares them.
# The client paces itself a bit UNDER the plan so it doesn't depend on FACTS
# counting exactly the way we do: 80% of the per-second limit, 90% of the
# per-minute limit (10/100 -> 8/90; 10/600 -> 8/540).
def _paced_limits(per_second: int, per_minute: int) -> tuple[int, int]:
    return max(1, int(per_second * 0.8)), max(1, int(per_minute * 0.9))


class _RateLimiter:
    """Blocks just long enough that no sliding 1-second or 60-second window
    ever holds more than the allowed number of requests."""

    def __init__(self, per_second: int, per_minute: int, clock=time.monotonic, sleep=time.sleep):
        self.per_second = per_second
        self.per_minute = per_minute
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()

    def wait(self) -> None:
        while True:
            now = self._clock()
            while self._stamps and now - self._stamps[0] >= 60:
                self._stamps.popleft()

            delay = 0.0
            if len(self._stamps) >= self.per_minute:
                delay = 60 - (now - self._stamps[0])
            elif len(self._stamps) >= self.per_second:
                oldest_in_second = self._stamps[-self.per_second]
                if now - oldest_in_second < 1:
                    delay = 1 - (now - oldest_in_second)

            if delay <= 0:
                self._stamps.append(now)
                return
            delay += 0.01
            if delay > 3:
                logger.info("Pausing %.0fs to stay under FACTS's per-minute request limit.", delay)
            self._sleep(delay)


def _retry_wait(attempt: int, resp: requests.Response | None = None) -> float:
    """How long to wait before retrying. If FACTS says how long (a
    Retry-After header, in seconds), wait that. Otherwise back off
    exponentially: 1.5s, 3s, 6s, 12s, ... capped at 60s."""
    if resp is not None:
        header = resp.headers.get("Retry-After")
        if header:
            try:
                return min(float(header), MAX_RETRY_WAIT_SECONDS)
            except ValueError:
                pass
    return min(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_RETRY_WAIT_SECONDS)


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
                # FACTS requires BOTH headers on every request (confirmed
                # against a live 200 OK from the FACTS Developer Portal's
                # own request tester):
                "Ocp-Apim-Subscription-Key": settings.subscription_key,
                "Facts-Api-Key": settings.api_key,
                "Accept": "application/json",
            }
        )
        self._limiter = _RateLimiter(*_paced_limits(settings.rate_limit_per_second, settings.rate_limit_per_minute))
        self.request_count = 0

    def _request(self, method: str, path: str, params: dict | None = None, **kwargs) -> requests.Response:
        url = self.settings.base_url.rstrip("/") + path
        params = dict(params or {})
        params.setdefault("api-version", self.settings.api_version)

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._limiter.wait()
            self.request_count += 1
            try:
                resp = self.session.request(method, url, params=params, timeout=30, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("Request to %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
                time.sleep(_retry_wait(attempt))
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(
                    "FACTS API returned %d for %s (attempt %d/%d); retrying",
                    resp.status_code, url, attempt, MAX_RETRIES,
                )
                time.sleep(_retry_wait(attempt, resp))
                continue

            if not resp.ok:
                message = _extract_error_message(resp)
                if resp.status_code in (401, 403):
                    message += (
                        " (A 401/403 on every request usually means FACTS_SUBSCRIPTION_KEY and/or "
                        "FACTS_API_KEY in .env is wrong -- FACTS requires BOTH: the short subscription "
                        "key in Ocp-Apim-Subscription-Key and the long school-scoped API key in "
                        "Facts-Api-Key. Double check neither is blank and they haven't been swapped.)"
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