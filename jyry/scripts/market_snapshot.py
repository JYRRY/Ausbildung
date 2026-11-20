"""Record today's Ausbildung market snapshot to a gzipped JSON file.

Needs only network access (no database), so GitHub Actions can run it daily::

    python -m jyry.scripts.market_snapshot --out-dir data/market

Exit code 1 when the Germany-wide count could not be fetched (nothing is
written then); per-Bundesland failures are recorded inside the file.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from jyry.scripts.ba_health import _ba_settings
from jyry.services.bundesagentur import BundesagenturClient
from jyry.services.market_snapshot import take_snapshot, write_snapshot


async def _main(out_dir: Path) -> int:
    async with BundesagenturClient(_ba_settings()) as client:
        snapshot = await take_snapshot(client)
    if snapshot["germany"] is None:
        print(f"Germany-wide count failed: {snapshot['errors']}", file=sys.stderr)
        return 1
    path = write_snapshot(snapshot, out_dir)
    print(
        f"{snapshot['date']}: {snapshot['germany']['total']} postings in Germany, "
        f"{len(snapshot['states'])}/16 states, {len(snapshot['errors'])} error(s) -> {path}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path("data/market"))
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.out_dir)))


if __name__ == "__main__":
    main()
