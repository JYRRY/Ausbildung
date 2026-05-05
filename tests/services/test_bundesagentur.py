"""Tests for jyry.services.bundesagentur."""

from __future__ import annotations

import httpx
import pytest
import respx

from jyry.services.bundesagentur import (
    BundesagenturClient,
    JobDetail,
    SearchHit,
    SearchPage,
)
from tests.conftest import load_fixture

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"


@pytest.fixture
def client(settings):
    return BundesagenturClient(settings)


@pytest.mark.asyncio
async def test_search_parses_hits_and_sends_api_key(settings):
    fixture = load_fixture("ba_search_page.json")
    async with BundesagenturClient(settings) as bac, respx.mock(
        assert_all_called=True
    ) as router:
        route = router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        page = await bac.search(was="Bäcker", wo="Bayern", size=100, page=1)

    assert isinstance(page, SearchPage)
    assert page.total == 3
    assert len(page.hits) == 3
    assert all(isinstance(h, SearchHit) for h in page.hits)

    first = page.hits[0]
    assert first.hash_id == "AAAA-hash-1"
    assert first.employer == "Konditorei Müller GmbH"
    assert first.kundennummer_hash == "kn-hash-aaaa-1"
    assert first.location_city == "München"
    assert first.location_region == "Bayern"

    second = page.hits[1]
    assert second.kundennummer_hash is None  # nullable in the schema

    request = route.calls.last.request
    assert request.headers["X-API-Key"] == settings.ba_api_key
    assert request.url.params["was"] == "Bäcker"
    assert request.url.params["wo"] == "Bayern"
    assert request.url.params["angebotsart"] == "4"
    assert request.url.params["page"] == "1"
    assert request.url.params["size"] == "100"


@pytest.mark.asyncio
async def test_fetch_detail_parses_payload(settings):
    fixture = load_fixture("ba_detail_with_email.json")
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobdetails/AAAA-hash-1").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        detail = await bac.fetch_detail("AAAA-hash-1")

    assert isinstance(detail, JobDetail)
    assert detail.hash_id == "AAAA-hash-1"
    assert detail.employer == "Konditorei Müller GmbH"
    assert detail.title and "Bäcker" in detail.title
    assert detail.description and "bewerbung@konditorei-mueller.de" in detail.description
    assert detail.employer_address == fixture["arbeitgeberAdresse"]


@pytest.mark.asyncio
async def test_search_retries_then_succeeds_on_5xx(settings):
    fixture = load_fixture("ba_search_page.json")
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=fixture),
            ]
        )
        page = await bac.search(was="Bäcker")

    assert page.total == 3
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_search_raises_after_three_failures(settings):
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await bac.search(was="Bäcker")

    assert route.call_count == 3


@pytest.mark.asyncio
async def test_non_retryable_4xx_does_not_retry(settings):
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(400)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await bac.search(was="Bäcker")

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_aclose_idempotent_when_client_externally_owned(settings):
    async with httpx.AsyncClient() as external:
        bac = BundesagenturClient(settings, client=external)
        await bac.aclose()
        # External client must remain usable.
        assert not external.is_closed
