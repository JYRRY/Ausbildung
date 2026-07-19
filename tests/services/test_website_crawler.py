"""Tests for jyry.services.website_crawler (mocked HTTP via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from jyry.services.website_crawler import WebsiteCrawler


class _CrawlSettings:
    crawl_max_pages = 5
    crawl_request_timeout_seconds = 2.0
    crawl_total_timeout_seconds = 5.0
    crawl_delay_seconds = 0.0
    crawl_max_html_bytes = 500_000
    crawl_max_concurrent = 3
    crawl_accept_generic_localparts = True


def _html(status: int = 200, body: str = "", ctype: str = "text/html"):
    return httpx.Response(status, text=body, headers={"content-type": ctype})


@pytest.mark.asyncio
@respx.mock
async def test_crawl_finds_email_on_contact_page():
    # Register the specific page first so it wins over the host-wide fallback.
    respx.get("https://firma-x.de/kontakt").mock(
        return_value=_html(
            body="<p>Ansprechpartner: Herr Klaus Meier — bewerbung@firma-x.de</p>"
        )
    )
    respx.route(method="GET", host="firma-x.de").mock(
        return_value=_html(body="<p>willkommen</p>")
    )

    crawler = WebsiteCrawler(_CrawlSettings())
    try:
        result = await crawler.crawl("firma-x.de")
    finally:
        await crawler.aclose()

    assert result.email == "bewerbung@firma-x.de"
    assert result.contact_person == "Herr Klaus Meier"
    assert result.website_url == "https://firma-x.de"


@pytest.mark.asyncio
@respx.mock
async def test_crawl_stops_early_on_preferred_email():
    home = respx.get("https://firma-x.de").mock(
        return_value=_html(body="<a href='mailto:karriere@firma-x.de'>x</a>")
    )
    kontakt = respx.get("https://firma-x.de/kontakt").mock(return_value=_html(body="x"))

    crawler = WebsiteCrawler(_CrawlSettings())
    try:
        result = await crawler.crawl("https://firma-x.de")
    finally:
        await crawler.aclose()

    assert result.email == "karriere@firma-x.de"
    assert home.called
    assert not kontakt.called  # stopped after the preferred hit on the homepage


@pytest.mark.asyncio
@respx.mock
async def test_crawl_respects_page_budget():
    settings = _CrawlSettings()
    settings.crawl_max_pages = 2  # type: ignore[misc]
    respx.get(url__regex=r"https://firma-x\.de.*").mock(
        return_value=_html(body="<p>kein email hier</p>")
    )

    crawler = WebsiteCrawler(settings)
    try:
        result = await crawler.crawl("https://firma-x.de")
    finally:
        await crawler.aclose()

    assert result.email is None
    assert result.pages_fetched == 2


@pytest.mark.asyncio
@respx.mock
async def test_crawl_skips_non_html():
    respx.get("https://firma-x.de").mock(
        return_value=_html(body="bewerbung@firma-x.de", ctype="application/pdf")
    )
    respx.get(url__regex=r"https://firma-x\.de/.+").mock(return_value=_html(404))

    crawler = WebsiteCrawler(_CrawlSettings())
    try:
        result = await crawler.crawl("https://firma-x.de")
    finally:
        await crawler.aclose()

    assert result.email is None


@pytest.mark.asyncio
@respx.mock
async def test_crawl_never_raises_on_connect_error():
    respx.get(url__regex=r"https?://firma-x\.de.*").mock(
        side_effect=httpx.ConnectError("boom")
    )

    crawler = WebsiteCrawler(_CrawlSettings())
    try:
        result = await crawler.crawl("https://firma-x.de")
    finally:
        await crawler.aclose()

    assert result.email is None
    assert result.website_url == "https://firma-x.de"


@pytest.mark.asyncio
async def test_crawl_none_url_returns_empty():
    crawler = WebsiteCrawler(_CrawlSettings())
    try:
        result = await crawler.crawl(None)
    finally:
        await crawler.aclose()
    assert result == result.__class__()
