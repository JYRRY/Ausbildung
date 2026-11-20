"""Tests for the BA health check and the hourly watch job."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from jyry.jobs.ba_health_watch import REMIND_EVERY, BaHealthWatch, run_ba_health_watch
from jyry.services.ba_health import (
    MIN_EXPECTED_TOTAL,
    HealthReport,
    check_ba,
    format_status,
)
from jyry.services.bundesagentur import BundesagenturClient
from tests.conftest import CODE_A, load_fixture

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"


def _healthy_search() -> dict:
    payload = copy.deepcopy(load_fixture("ba_search_page.json"))
    payload["maxErgebnisse"] = 5000
    payload["woOutput"] = {"bereinigterOrt": "Hessen", "suchmodus": "BUNDESLANDSUCHE"}
    return payload


def _mock(router, *, search=None, search_status=200, detail=None, detail_status=200):
    router.get(f"{BASE}/pc/v6/jobs").mock(
        return_value=httpx.Response(search_status, json=search or {})
    )
    router.get(f"{BASE}/pc/v4/jobdetails/{CODE_A}").mock(
        return_value=httpx.Response(
            detail_status, json=detail or load_fixture("ba_detail_with_email.json")
        )
    )


@pytest.mark.asyncio
async def test_healthy_api_reports_ok(settings):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        _mock(router, search=_healthy_search())
        report = await check_ba(client)
    assert report.ok, report.problems
    assert report.search_total == 5000
    assert report.sample_refnr == "10000-1234567890-S"
    assert "يعمل" in format_status(report)


@pytest.mark.asyncio
async def test_retired_search_endpoint_is_reported(settings):
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        _mock(router, search_status=403)
        report = await check_ba(client)
    assert not report.ok
    assert "HTTP 403" in report.problems[0]


@pytest.mark.asyncio
async def test_renamed_result_list_is_reported(settings):
    payload = _healthy_search()
    payload["stellenangebote"] = payload.pop("ergebnisliste")  # shape changed
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        _mock(router, search=payload)
        report = await check_ba(client)
    assert not report.ok
    assert any("referenznummer" in p for p in report.problems)


@pytest.mark.asyncio
async def test_suspiciously_few_results_are_reported(settings):
    payload = _healthy_search()
    payload["maxErgebnisse"] = MIN_EXPECTED_TOTAL - 1
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        _mock(router, search=payload)
        report = await check_ba(client)
    assert not report.ok
    assert str(MIN_EXPECTED_TOTAL - 1) in report.problems[0]


@pytest.mark.asyncio
async def test_missing_fields_and_broken_detail_are_reported(settings):
    payload = _healthy_search()
    for item in payload["ergebnisliste"]:
        item.pop("firma")
        item.pop("stellenlokationen")
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        _mock(router, search=payload, detail_status=404)
        report = await check_ba(client)
    text = " | ".join(report.problems)
    assert "firma" in text
    assert "stellenlokationen" in text
    assert "HTTP 404" in text


@pytest.mark.asyncio
async def test_state_search_falling_back_to_a_village_is_reported(settings):
    payload = _healthy_search()
    payload["woOutput"] = {
        "bereinigterOrt": "Hessen bei Halberstadt",
        "suchmodus": "UMKREISSUCHE",
    }
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        _mock(router, search=payload)
        report = await check_ba(client)
    assert not report.ok
    assert "Hessen bei Halberstadt" in report.problems[-1]


# ── watch job: alert on break, remind, all-clear on recovery ─────────────────

_BROKEN = HealthReport(problems=["البحث فشل: HTTP 403"])
_HEALTHY = HealthReport(search_total=5000, sample_refnr="X")


def test_watch_silent_while_healthy():
    watch = BaHealthWatch()
    assert watch.message_for(_HEALTHY) is None
    assert watch.message_for(_HEALTHY) is None


def test_watch_alerts_once_then_reminds_then_recovers():
    clock = [datetime(2026, 11, 20, 8, tzinfo=UTC)]
    watch = BaHealthWatch(now=lambda: clock[0])
    watch.message_for(_HEALTHY)

    first = watch.message_for(_BROKEN)
    assert first is not None and "HTTP 403" in first

    clock[0] += timedelta(hours=1)
    assert watch.message_for(_BROKEN) is None  # no spam every hour

    clock[0] += REMIND_EVERY
    assert watch.message_for(_BROKEN) is not None  # reminder

    clock[0] += timedelta(hours=1)
    recovered = watch.message_for(_HEALTHY)
    assert recovered is not None and "عاد يعمل" in recovered
    assert watch.message_for(_HEALTHY) is None


def test_watch_alerts_when_broken_at_startup():
    assert BaHealthWatch().message_for(_BROKEN) is not None


@pytest.mark.asyncio
async def test_run_messages_every_admin_on_failure(settings):
    sent: list[tuple[int, str]] = []

    async def notify(chat_id: int, text: str) -> bool:
        sent.append((chat_id, text))
        return True

    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        _mock(router, search_status=403)
        report = await run_ba_health_watch(
            watch=BaHealthWatch(), client=client, admin_ids=[11, 22], notify=notify
        )
    assert not report.ok
    assert [chat for chat, _ in sent] == [11, 22]
