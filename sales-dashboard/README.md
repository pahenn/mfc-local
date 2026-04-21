# Sales Dashboard

Single-file, browser-only dashboard for exploring MFC sales data. Runs entirely client-side via DuckDB-WASM — nothing leaves the machine.

## Usage

1. Double-click `dashboard.html` (or open in Chrome / Edge / Safari / Firefox — any modern browser).
2. On the **Load data** tab, drop or pick your CSVs. Filenames must contain `header`, `detail`, or `account`.
3. The Executive Report populates automatically once data is loaded.

## Expected CSVs

Reference copies (or the analyst drop zone) live in [source-data/](./source-data/). See [source-data/README.md](./source-data/README.md) for the column contract.

## Sample data (while you wait for the real extract)

Realistic synthetic CSVs are already generated in [source-data/](./source-data/). They model:

- **Chicago Co-op Fleet Services** as a parent org with 8 child fleets (exercises Q1 rollup + Q4)
- Two other parent orgs + 15 standalone accounts across all size tiers (exercises Q6)
- 3+ years of invoices with 8% YoY growth and fall-peak seasonality (exercises Q2, Q3)
- 18 service/product SKUs mapping into the five Q5 buckets
- 5 cancelled accounts spread across the past 4–22 months with cancellation reasons (exercises Q9, Q10, Q11)
- 2 inactive accounts (no invoices in 14 months) (exercises Q7)

Regenerate at any time:

```bash
python3 scripts/generate_sample_data.py

# Or pin the "as-of" date for reproducibility:
SAMPLE_DATA_AS_OF=2026-04-21 python3 scripts/generate_sample_data.py
```

Uses stdlib only — no `uv install` required.

## Tabs

- **Load data** — drop zone + load log.
- **Executive Report** — pre-baked answers to the stakeholder questions (Q2, Q3, Q5, Q6, Q7, Q9, Q10, Q11). Cards that need `accounts.csv` show a clear "missing" message until it's loaded.
- **Account Explorer** — pick any parent org (or account id), optional date range, see monthly billings + service breakdown. This answers Q1 for any customer, not just Chicago Co-op.
- **Raw SQL** — ad-hoc queries against the loaded tables.
- **About / Schema** — the column contract and current open questions.

## Tech

- [Vue 3](https://vuejs.org) from esm.sh
- [@duckdb/duckdb-wasm](https://github.com/duckdb/duckdb-wasm) from jsdelivr (via internal bundle selection)
- [Observable Plot](https://observablehq.com/plot) from esm.sh

All three load over HTTPS from CDN at page open. The HTML file itself has no JS bundled — it's ~900 lines of source you can inspect.

## Known constraints

- **First open needs internet** — the CDN deps load once, then the browser caches them. Offline on subsequent opens works if the browser cache hasn't been cleared.
- **Web Worker on `file://`** — uses the Blob-worker pattern so DuckDB's worker initializes from a `file://` page. Tested on Chrome/Safari/Firefox.
- **Not optimized for millions of rows** — fine up to a few million; for larger data convert to Parquet first and swap `read_csv_auto` for `read_parquet`.

## Open questions driving the design

See the **About / Schema** tab inside the dashboard, or the parent CLAUDE.md work log, for the list of stakeholder questions this is designed to answer and which ones still need decisions from the data team (bucket thresholds for Q6, "lost revenue" definition for Q10, etc).
