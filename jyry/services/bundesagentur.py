"""Async client for the Bundesagentur für Arbeit Jobsuche API (v4).

Returns immutable dataclasses so callers don't depend on raw JSON shapes.
Retries 5xx and transport errors three times with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
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

_DETAIL_PATH_TEMPLATE = "/pc/v4/jobdetails/{hash_id}"
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_DETAIL_CONCURRENCY = 5


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One Stellenangebot row from /pc/v4/jobs."""

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
    """One page of /pc/v4/jobs results."""

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


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError | httpx.RemoteProtocolError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600 or exc.response.status_code == 429
    return False


def _parse_hit(payload: dict[str, Any]) -> SearchHit:
    arbeitsort = payload.get("arbeitsort") or {}
    return SearchHit(
        hash_id=str(payload["hashId"]),
        refnr=payload.get("refnr"),
        employer=payload.get("arbeitgeber"),
        kundennummer_hash=payload.get("kundennummerHash"),
        location_city=arbeitsort.get("ort"),
        location_plz=arbeitsort.get("plz"),
        location_region=arbeitsort.get("region"),
        external_url=payload.get("externeUrl"),
        profession=payload.get("beruf"),
        raw=payload,
    )


def _parse_detail(payload: dict[str, Any]) -> JobDetail:
    return JobDetail(
        hash_id=str(payload.get("hashId") or payload.get("encryptedJobCode") or ""),
        refnr=payload.get("refnr") or payload.get("referenznummer"),
        employer=payload.get("arbeitgeber"),
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
            base_url=settings.ba_api_base.rstrip("/").removesuffix("/pc/v4/jobs"),
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

        payload = await self._request_json("GET", "/pc/v4/jobs", params=params)
        raw_hits = payload.get("stellenangebote") or []
        hits = tuple(_parse_hit(item) for item in raw_hits if item.get("hashId"))
        total = int(payload.get("maxErgebnisse") or len(hits))
        return SearchPage(hits=hits, total=total, page=page, size=size)

    async def fetch_detail(self, hash_id: str) -> JobDetail:
        """GET /pc/v4/jobdetails/{hash_id}. Concurrency-limited."""
        async with self._detail_sem:
            payload = await self._request_json(
                "GET", _DETAIL_PATH_TEMPLATE.format(hash_id=hash_id)
            )
            if not payload.get("hashId"):
                payload["hashId"] = hash_id
            return _parse_detail(payload)
