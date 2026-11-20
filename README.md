# Market snapshots (data only)

One file per day, written by `.github/workflows/market-snapshot.yml` on `main`:

    market/<YYYY>/<YYYY-MM-DD>.json.gz

Each file is gzipped JSON with the Ausbildung posting total for Germany and
for each of the 16 Bundesländer, plus the Bundesagentur's facet counts
(profession, field, city, employer, start date, new in the last 1/7/14/28
days). Read one with:

    python -c "from pathlib import Path; from jyry.services.market_snapshot import read_snapshot; print(read_snapshot(Path('market/2026/2026-11-20.json.gz'))['germany']['total'])"

This branch holds data only and is never merged into `main`.
