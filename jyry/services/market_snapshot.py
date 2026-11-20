"""Daily snapshot of the Ausbildung market from the Bundesagentur search.

One request per scope (Germany, then each Bundesland) returns the total and
the facet counts the BA computes for it: by profession (``beruf``), field
(``berufsfeld``), city (``arbeitsort``), employer, start date
(``eintrittsdatum``), freshness (``veroeffentlichtseit``: new in the last
1/7/14/28 days) and more. The facets are stored whole, so later features
(monthly trend cards, seasonal forecasts) can be computed from history that
was never thrown away.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jyry.constants import STATE_SEARCH_TERMS
from jyry.services.bundesagentur import BundesagenturClient, MarketCounts

SCHEMA_VERSION = 1
_BERLIN = ZoneInfo("Europe/Berlin")
_PAUSE_BETWEEN_REQUESTS = 0.5  # politeness towards the public API


def _scope_entry(counts: MarketCounts) -> dict[str, Any]:
    return {
        "total": counts.total,
        "search_mode": counts.search_mode,
        "resolved_place": counts.resolved_place,
        "facets": counts.facets,
    }


async def take_snapshot(
    client: BundesagenturClient,
    *,
    now: datetime | None = None,
    pause: float = _PAUSE_BETWEEN_REQUESTS,
) -> dict[str, Any]:
    """Collect Germany-wide and per-Bundesland counts. A failing scope is
    recorded under ``errors`` instead of aborting the whole snapshot."""
    taken_at = (now or datetime.now(tz=_BERLIN)).astimezone(_BERLIN)
    snapshot: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "date": taken_at.date().isoformat(),
        "taken_at": taken_at.isoformat(timespec="seconds"),
        "source": "bundesagentur-jobsuche/v6",
        "angebotsart": 4,
        "germany": None,
        "states": {},
        "errors": {},
    }

    scopes: list[tuple[str, str | None]] = [("DE", None)]
    scopes += list(STATE_SEARCH_TERMS.items())
    for i, (code, wo) in enumerate(scopes):
        if i:
            await asyncio.sleep(pause)
        try:
            counts = await client.fetch_market_counts(wo=wo)
        except Exception as exc:  # recorded, the other scopes still count
            snapshot["errors"][code] = f"{type(exc).__name__}: {exc}"[:300]
            continue
        entry = _scope_entry(counts)
        if code == "DE":
            snapshot["germany"] = entry
        else:
            snapshot["states"][code] = entry
            if counts.search_mode != "BUNDESLANDSUCHE":
                snapshot["errors"][code] = (
                    f"not a state-wide search: {counts.search_mode} "
                    f"-> {counts.resolved_place}"
                )
    return snapshot


def snapshot_path(out_dir: Path, date_iso: str) -> Path:
    """``<out_dir>/<YYYY>/<YYYY-MM-DD>.json.gz``."""
    return out_dir / date_iso[:4] / f"{date_iso}.json.gz"


def write_snapshot(snapshot: dict[str, Any], out_dir: Path) -> Path:
    path = snapshot_path(out_dir, snapshot["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    # mtime=0 keeps the file byte-identical for identical content.
    path.write_bytes(gzip.compress(data, mtime=0))
    return path


def read_snapshot(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(gzip.decompress(path.read_bytes()))
    return payload


__all__ = [
    "SCHEMA_VERSION",
    "read_snapshot",
    "snapshot_path",
    "take_snapshot",
    "write_snapshot",
]
