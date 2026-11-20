"""Async client for the Bundesagentur für Arbeit Jobsuche API.

Search uses ``/pc/v6/jobs`` — the v4 search endpoint was retired and answers
403. Job details still live at ``/pc/v4/jobdetails/{code}``, where ``code`` is
the base64 of the posting's ``referenznummer`` (v6 hits carry no ``hashId``).

Returns immutable dataclasses so callers don't depend on raw JSON shapes.
Retries 5xx and transport errors three times with exponential backoff.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from jyry.config import Settings

logger = logging.getLogger(__name__)

_SEARCH_PATH = "/pc/v6/jobs"
_DETAIL_PATH_TEMPLATE = "/pc/v4/jobdetails/{hash_id}"
# BA_API_BASE may still carry a search-path suffix from older .env files.
_SEARCH_SUFFIX_RE = re.compile(r"/pc/v\d+/jobs/?$")
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_DETAIL_CONCURRENCY = 5


def encode_job_code(refnr: str) -> str:
    """Detail-endpoint key for a posting: base64 of its ``referenznummer``."""
    return base64.b64encode(refnr.encode("utf-8")).decode("ascii")


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One Stellenangebot row from /pc/v6/jobs."""

    hash_id: str
    refnr: str | None
    employer: str | None
    kundennummer_hash: str | None
    location_city: str | None
    location_plz: str | None
    location_region: str | None
    external_url: str | None
    profession: str | None
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class SearchPage:
    """One page of /pc/v6/jobs results."""

    hits: tuple[SearchHit, ...]
    total: int
    page: int
    size: int


@dataclass(frozen=True, slots=True)
class JobDetail:
    """One Stellenangebot detail body from /pc/v4/jobdetails/{hash}."""

    hash_id: str
    refnr: str | None
    employer: str | None
    employer_kundennummer_hash: str | None
    title: str | None
    description: str | None
    employer_address: dict[str, Any] | None
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True, slots=True)
class MarketCounts:
    """Posting totals plus the search's facet counts (by profession, city …)."""

    total: int
    facets: dict[str, Any]
    # How the BA understood ``wo``: "BUNDESLANDSUCHE" (whole state),
    # "UMKREISSUCHE" (radius around a place) or None (no ``wo``).
    search_mode: str | None = None
    resolved_place: str | None = None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError | httpx.RemoteProtocolError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600 or exc.response.status_code == 429
    return False


def _first_address(payload: dict[str, Any]) -> dict[str, Any]:
    locations = payload.get("stellenlokationen") or []
    if locations and isinstance(locations[0], dict):
        address = locations[0].get("adresse")
        if isinstance(address, dict):
            return address
    return {}


def _parse_hit(payload: dict[str, Any]) -> SearchHit:
    refnr = str(payload["referenznummer"])
    address = _first_address(payload)
    return SearchHit(
        hash_id=encode_job_code(refnr),
        refnr=refnr,
        employer=payload.get("firma"),
        # v6 hits no longer expose the employer's customer-number hash; the
        # finder falls back to a name-based employer ref.
        kundennummer_hash=payload.get("kundennummerHash"),
        location_city=address.get("ort"),
        location_plz=address.get("plz"),
        location_region=address.get("region"),
        external_url=payload.get("externeURL"),
        profession=payload.get("hauptberuf"),
        raw=payload,
    )


def _parse_detail(payload: dict[str, Any]) -> JobDetail:
    return JobDetail(
        hash_id=str(payload.get("hashId") or payload.get("encryptedJobCode") or ""),
        refnr=payload.get("refnr") or payload.get("referenznummer"),
        employer=payload.get("firma") or payload.get("arbeitgeber"),
        employer_kundennummer_hash=payload.get("arbeitgeberKundennummerHash"),
        title=payload.get("stellenangebotsTitel") or payload.get("titel"),
        description=(
            payload.get("stellenangebotsBeschreibung") or payload.get("stellenbeschreibung")
        ),
        employer_address=payload.get("arbeitgeberAdresse"),
        raw=payload,
    )


class BundesagenturClient:
    """Async wrapper around the Bundesagentur Jobsuche API."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        detail_concurrency: int = _DETAIL_CONCURRENCY,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            base_url=_SEARCH_SUFFIX_RE.sub("", settings.ba_api_base.rstrip("/")),
            timeout=_DEFAULT_TIMEOUT,
            headers={
                "X-API-Key": settings.ba_api_key,
                "Accept": "application/json",
                "User-Agent": "JYRY-AI/0.1 (+https://github.com/JYRRY/Ausbildung)",
            },
            http2=False,
        )
        self._detail_sem = asyncio.Semaphore(detail_concurrency)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
                before_sleep=before_sleep_log(logger, logging.WARNING),
            ):
                with attempt:
                    response = await self._client.request(method, url, **kwargs)
                    response.raise_for_status()
                    payload: dict[str, Any] = response.json()
                    return payload
        except RetryError as exc:  # pragma: no cover - tenacity raises original via reraise
            raise exc.last_attempt.exception() or exc from None
        raise RuntimeError("unreachable")

    async def search(
        self,
        *,
        was: str,
        wo: str | None = None,
        angebotsart: int = 4,
        page: int = 1,
        size: int = 100,
        umkreis: int | None = None,
    ) -> SearchPage:
        """List Ausbildung postings matching the given filters.

        `angebotsart=4` selects Ausbildung/Duales Studium.
        """
        params: dict[str, str | int] = {
            "was": was,
            "angebotsart": angebotsart,
            "page": page,
            "size": size,
        }
        if wo:
            params["wo"] = wo
        if umkreis is not None:
            params["umkreis"] = umkreis

        payload = await self._request_json("GET", _SEARCH_PATH, params=params)
        raw_hits = payload.get("ergebnisliste") or []
        hits = tuple(_parse_hit(item) for item in raw_hits if item.get("referenznummer"))
        total = int(payload.get("maxErgebnisse") or len(hits))
        return SearchPage(hits=hits, total=total, page=page, size=size)

    async def fetch_market_counts(
        self, *, wo: str | None = None, angebotsart: int = 4
    ) -> MarketCounts:
        """Totals and facet counts for every posting matching ``wo`` (no
        profession filter). One request with a single result row."""
        params: dict[str, str | int] = {"angebotsart": angebotsart, "page": 1, "size": 1}
        if wo:
            params["wo"] = wo
        payload = await self._request_json("GET", _SEARCH_PATH, params=params)
        facets = payload.get("facetten")
        where = payload.get("woOutput")
        where = where if isinstance(where, dict) else {}
        return MarketCounts(
            total=int(payload.get("maxErgebnisse") or 0),
            facets=facets if isinstance(facets, dict) else {},
            search_mode=where.get("suchmodus"),
            resolved_place=where.get("bereinigterOrt"),
        )

    async def fetch_detail(self, hash_id: str) -> JobDetail:
        """GET /pc/v4/jobdetails/{hash_id}, where ``hash_id`` is the
        ``encode_job_code`` of the posting. Concurrency-limited."""
        async with self._detail_sem:
            payload = await self._request_json(
                "GET", _DETAIL_PATH_TEMPLATE.format(hash_id=hash_id)
            )
            if not payload.get("hashId"):
                payload["hashId"] = hash_id
            return _parse_detail(payload)
