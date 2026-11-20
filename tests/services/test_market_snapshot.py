"""Tests for the daily market snapshot."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from jyry.constants import STATE_SEARCH_TERMS
from jyry.services.bundesagentur import BundesagenturClient
from jyry.services.market_snapshot import (
    read_snapshot,
    snapshot_path,
    take_snapshot,
    write_snapshot,
)

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
NOW = datetime(2026, 11, 20, 6, 30, tzinfo=ZoneInfo("Europe/Berlin"))


def _answer(request: httpx.Request) -> httpx.Response:
    wo = request.url.params.get("wo")
    if wo == STATE_SEARCH_TERMS["SN"]:
        return httpx.Response(503)
    where = (
        {"bereinigterOrt": "Sachsen bei Ansbach", "suchmodus": "UMKREISSUCHE"}
        if wo == STATE_SEARCH_TERMS["BE"]
        else {"bereinigterOrt": wo, "suchmodus": "BUNDESLANDSUCHE"} if wo else None
    )
    body = {
        "ergebnisliste": [],
        "maxErgebnisse": 1000 if wo else 200_000,
        "facetten": {"beruf": {"counts": {"Bäcker/in": 7}, "maxCount": 7}},
    }
    if where:
        body["woOutput"] = where
    return httpx.Response(200, json=body)


@pytest.mark.asyncio
async def test_snapshot_covers_germany_and_every_state(settings):
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        route = router.get(f"{BASE}/pc/v6/jobs").mock(side_effect=_answer)
        snap = await take_snapshot(client, now=NOW, pause=0)

    assert snap["date"] == "2026-11-20"
    assert snap["germany"]["total"] == 200_000
    assert snap["germany"]["facets"]["beruf"]["counts"] == {"Bäcker/in": 7}
    # every request is an Ausbildung-only, one-row query
    first = route.calls[0].request.url.params
    assert first["angebotsart"] == "4" and first["size"] == "1" and "wo" not in first
    # 16 states asked; Sachsen failed (503) and is recorded, not fatal
    assert len(route.calls) >= 17
    assert "SN" not in snap["states"] and "SN" in snap["errors"]
    assert len(snap["states"]) == 15
    assert snap["states"]["BY"]["search_mode"] == "BUNDESLANDSUCHE"
    # a state that silently became a radius search is flagged
    assert "UMKREISSUCHE" in snap["errors"]["BE"]


def test_write_and_read_round_trip(tmp_path):
    snap = {"date": "2026-11-20", "germany": {"total": 1}, "states": {}, "errors": {}}
    path = write_snapshot(snap, tmp_path)
    assert path == snapshot_path(tmp_path, "2026-11-20")
    assert path.name == "2026-11-20.json.gz" and path.parent.name == "2026"
    assert read_snapshot(path) == snap
    # identical content -> identical bytes (no noisy diffs in git)
    first = path.read_bytes()
    write_snapshot(snap, tmp_path)
    assert path.read_bytes() == first
