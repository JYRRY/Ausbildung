"""Tests for jyry.services.job_finder."""

from __future__ import annotations

import copy
from datetime import timedelta

import httpx
import pytest
import respx

from jyry.services.bundesagentur import BundesagenturClient
from jyry.services.job_finder import iter_ready_postings
from tests.conftest import load_fixture

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"


def _empty_page() -> dict:
    return {"stellenangebote": [], "maxErgebnisse": 0, "page": 1, "size": 100}


@pytest.fixture
def search_payload() -> dict:
    # Three hits — A (good email), B (no email), C (only generic emails).
    return load_fixture("ba_search_page.json")


def _detail_route(router, hash_id: str, fixture_name: str):
    return router.get(f"{BASE}/pc/v4/jobdetails/{hash_id}").mock(
        return_value=httpx.Response(200, json=load_fixture(fixture_name))
    )


@pytest.mark.asyncio
async def test_yields_only_postings_with_recoverable_email(
    settings, db_session, search_payload
):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=search_payload),
                httpx.Response(200, json=_empty_page()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        results = []
        async for posting in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=10,
            ttl=timedelta(hours=24),
            max_pages_per_query=2,
            page_size=100,
        ):
            results.append(posting)

    assert len(results) == 1
    only = results[0]
    assert only.email == "bewerbung@konditorei-mueller.de"
    assert only.company == "Konditorei Müller GmbH"
    assert only.state_code == "BY"
    assert only.specialty_keyword == "Bäcker"


@pytest.mark.asyncio
async def test_stops_iteration_when_want_satisfied(
    settings, db_session, search_payload
):
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        search_route = router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(200, json=search_payload)
        )
        detail_a = _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        produced = []
        async for p in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=1,
            ttl=timedelta(hours=24),
        ):
            produced.append(p)

        assert len(produced) == 1
        # We hit the first detail and immediately stopped — no second page,
        # no calls for B/C.
        assert search_route.call_count == 1
        assert detail_a.call_count == 1


@pytest.mark.asyncio
async def test_cached_employer_skips_detail_fetch(
    settings, db_session, search_payload
):
    """A second iteration finds rows in the cache and never re-hits /jobdetails."""
    # First pass — populate the cache.
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=search_payload),
                httpx.Response(200, json=_empty_page()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")
        async for _ in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=10,
            ttl=timedelta(hours=24),
        ):
            pass

    # Second pass — only the search endpoint should be hit; details are cache-served.
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=True
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=search_payload),
                httpx.Response(200, json=_empty_page()),
            ]
        )
        # Intentionally NO mocks for /jobdetails — any call would 404 in respx.

        results = []
        async for posting in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=10,
            ttl=timedelta(hours=24),
        ):
            results.append(posting)

    assert len(results) == 1
    assert results[0].email == "bewerbung@konditorei-mueller.de"


@pytest.mark.asyncio
async def test_same_employer_in_two_specialties_only_yielded_once(
    settings, db_session, search_payload
):
    """An employer appearing under two specialty searches must not duplicate."""
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=search_payload),
                httpx.Response(200, json=_empty_page()),
                httpx.Response(200, json=copy.deepcopy(search_payload)),
                httpx.Response(200, json=_empty_page()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        results = []
        async for posting in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker", "Koch"],
            states=["BY"],
            want=10,
            ttl=timedelta(hours=24),
        ):
            results.append(posting)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_detail_fetch_failure_does_not_abort_run(
    settings, db_session, search_payload
):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=search_payload),
                httpx.Response(200, json=_empty_page()),
            ]
        )
        # AAAA detail fails terminally with non-retryable 404.
        router.get(f"{BASE}/pc/v4/jobdetails/AAAA-hash-1").mock(
            return_value=httpx.Response(404)
        )
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_with_email.json")

        results = []
        async for posting in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=10,
            ttl=timedelta(hours=24),
        ):
            results.append(posting)

    assert len(results) == 1
    assert results[0].hash_id == "CCCC-hash-3"


@pytest.mark.asyncio
async def test_want_zero_emits_nothing(settings, db_session):
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(200, json=_empty_page())
        )
        results = []
        async for p in iter_ready_postings(
            db_session,
            client,
            specialties=["Bäcker"],
            states=["BY"],
            want=0,
            ttl=timedelta(hours=24),
        ):
            results.append(p)
    assert results == []
