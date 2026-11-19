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
    encode_job_code,
)
from tests.conftest import CODE_A, load_fixture

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
        route = router.get(f"{BASE}/pc/v6/jobs").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        page = await bac.search(was="Bäcker", wo="Bayern", size=100, page=1)

    assert isinstance(page, SearchPage)
    assert page.total == 3
    assert len(page.hits) == 3
    assert all(isinstance(h, SearchHit) for h in page.hits)

    first = page.hits[0]
    assert first.hash_id == CODE_A  # base64 of the referenznummer
    assert first.refnr == "10000-1234567890-S"
    assert first.employer == "Konditorei Müller GmbH"
    assert first.kundennummer_hash is None  # v6 hits no longer carry it
    assert first.location_city == "München"
    assert first.location_plz == "80331"
    assert first.location_region == "BAYERN"
    assert first.profession == "Bäcker/in"
    assert first.external_url is None

    second = page.hits[1]
    assert second.external_url == "https://example.com/apply"

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
        router.get(f"{BASE}/pc/v4/jobdetails/{CODE_A}").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        detail = await bac.fetch_detail(CODE_A)

    assert isinstance(detail, JobDetail)
    assert detail.hash_id == CODE_A
    assert detail.employer == "Konditorei Müller GmbH"
    assert detail.title and "Bäcker" in detail.title
    assert detail.description and "bewerbung@konditorei-mueller.de" in detail.description
    assert detail.employer_address == fixture["arbeitgeberAdresse"]


def test_encode_job_code_matches_documented_example():
    # Example from bundesAPI/jobsuche-api openapi.yaml (jobdetails parameter).
    assert encode_job_code("10001-1002716922-S") == "MTAwMDEtMTAwMjcxNjkyMi1T"


@pytest.mark.asyncio
async def test_search_skips_rows_without_referenznummer(settings):
    payload = {
        "ergebnisliste": [
            {"firma": "Ohne Nummer GmbH"},
            {"referenznummer": "10000-1234567890-S", "firma": "Mit Nummer GmbH"},
        ],
        "maxErgebnisse": 2,
    }
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        router.get(f"{BASE}/pc/v6/jobs").mock(
            return_value=httpx.Response(200, json=payload)
        )
        page = await bac.search(was="Bäcker")

    assert [h.employer for h in page.hits] == ["Mit Nummer GmbH"]
    assert page.total == 2


@pytest.mark.asyncio
async def test_legacy_base_url_suffix_still_hits_v6_search(settings):
    legacy = settings.model_copy(
        update={"ba_api_base": f"{BASE}/pc/v4/jobs"}  # pre-v6 .env value
    )
    fixture = load_fixture("ba_search_page.json")
    async with BundesagenturClient(legacy) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v6/jobs").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        page = await bac.search(was="Bäcker")

    assert route.called
    assert page.total == 3


@pytest.mark.asyncio
async def test_search_retries_then_succeeds_on_5xx(settings):
    fixture = load_fixture("ba_search_page.json")
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v6/jobs").mock(
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
        route = router.get(f"{BASE}/pc/v6/jobs").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await bac.search(was="Bäcker")

    assert route.call_count == 3


@pytest.mark.asyncio
async def test_non_retryable_4xx_does_not_retry(settings):
    async with BundesagenturClient(settings) as bac, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v6/jobs").mock(
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
