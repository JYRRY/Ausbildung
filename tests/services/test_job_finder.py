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


# ── employer-website crawl fallback ───────────────────────────────────────────

from datetime import datetime, timezone  # noqa: E402

from jyry.services import job_cache_repo  # noqa: E402
from jyry.services.job_cache_repo import fallback_employer_ref  # noqa: E402
from jyry.services.website_crawler import WebsiteCrawler  # noqa: E402


def _site(body: str, status: int = 200):
    return httpx.Response(status, text=body, headers={"content-type": "text/html"})


@pytest.mark.asyncio
async def test_crawl_fallback_recovers_email_and_contact(
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
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email_with_website.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")
        # Employer website: email recovered from the homepage.
        router.route(method="GET", host="anonyme-firma.de").mock(
            return_value=_site(
                "<p>Ansprechpartner Herr Klaus Meier — bewerbung@anonyme-firma.de</p>"
            )
        )

        crawler = WebsiteCrawler(settings)
        results = []
        async for posting in iter_ready_postings(
            db_session, client,
            specialties=["Bäcker"], states=["BY"], want=10,
            ttl=timedelta(hours=24), crawler=crawler, crawl_budget=10,
        ):
            results.append(posting)
        await crawler.aclose()

    emails = {p.email for p in results}
    assert "bewerbung@konditorei-mueller.de" in emails
    assert "bewerbung@anonyme-firma.de" in emails
    crawled = next(p for p in results if p.email == "bewerbung@anonyme-firma.de")
    assert crawled.contact_person == "Herr Klaus Meier"

    ref = fallback_employer_ref("Anonyme Firma")
    row = await job_cache_repo.get_fresh(db_session, ref, timedelta(hours=24))
    assert row is not None and row.crawl_attempted_at is not None


@pytest.mark.asyncio
async def test_crawl_not_repeated_when_already_attempted(settings, db_session):
    ref = fallback_employer_ref("Anonyme Firma")
    now = datetime.now(tz=timezone.utc)
    await job_cache_repo.upsert(
        db_session, employer_ref=ref, raw={}, email=None,
        company="Anonyme Firma", title="Bäcker", location=None,
        state_code="BY", specialty_keyword="Bäcker",
        website_url="https://anonyme-firma.de", crawl_attempted_at=now,
    )
    await db_session.commit()

    search = {
        "stellenangebote": [
            {"hashId": "BBBB-hash-2", "arbeitgeber": "Anonyme Firma",
             "kundennummerHash": None, "arbeitsort": {"ort": "Augsburg", "region": "BY"}}
        ],
        "maxErgebnisse": 1, "page": 1, "size": 100,
    }
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[httpx.Response(200, json=search),
                         httpx.Response(200, json=_empty_page())]
        )
        website = router.route(method="GET", host="anonyme-firma.de").mock(
            return_value=_site("bewerbung@anonyme-firma.de")
        )
        crawler = WebsiteCrawler(settings)
        results = [
            p async for p in iter_ready_postings(
                db_session, client, specialties=["Bäcker"], states=["BY"],
                want=10, ttl=timedelta(hours=24), crawler=crawler, crawl_budget=10,
            )
        ]
        await crawler.aclose()

    assert results == []
    assert website.call_count == 0  # already-attempted row is not re-crawled


@pytest.mark.asyncio
async def test_crawl_error_does_not_abort_run(settings, db_session, search_payload):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[httpx.Response(200, json=search_payload),
                         httpx.Response(200, json=_empty_page())]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email_with_website.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")
        router.route(method="GET", host="anonyme-firma.de").mock(
            side_effect=httpx.ConnectError("down")
        )
        crawler = WebsiteCrawler(settings)
        results = [
            p async for p in iter_ready_postings(
                db_session, client, specialties=["Bäcker"], states=["BY"],
                want=10, ttl=timedelta(hours=24), crawler=crawler, crawl_budget=10,
            )
        ]
        await crawler.aclose()

    assert [p.email for p in results] == ["bewerbung@konditorei-mueller.de"]


@pytest.mark.asyncio
async def test_no_crawler_keeps_legacy_behavior(settings, db_session, search_payload):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[httpx.Response(200, json=search_payload),
                         httpx.Response(200, json=_empty_page())]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email_with_website.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        results = [
            p async for p in iter_ready_postings(
                db_session, client, specialties=["Bäcker"], states=["BY"],
                want=10, ttl=timedelta(hours=24),  # no crawler
            )
        ]
    assert [p.email for p in results] == ["bewerbung@konditorei-mueller.de"]
