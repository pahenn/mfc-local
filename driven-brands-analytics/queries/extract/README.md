# MSSQL extracts

These are the raw table pulls from the MFC legacy SQL Server. Each file is a self-contained SELECT — no joins beyond what's needed for the scope filter (`corpType = 'T5C'` + date window).

## Run order & output file names

| # | Script | Output CSV | Rows (rough) |
|---|---|---|---|
| 01 | corporation_types.sql | `corporation_types.csv` | 1 |
| 02 | customers.sql | `customers.csv` | handful |
| 03 | customer_sites.sql | `customer_sites.csv` | hundreds (every Take 5 shop) |
| 04 | fleets.sql | `fleets.csv` | hundreds–low thousands |
| 05 | invoices.sql | `invoices.csv` | tens–hundreds of thousands (4 months) |
| 06 | invoice_item_bridge.sql | `invoice_item_bridge.csv` | 2–5× invoices.csv |

## Scope

- **Brand**: `corpType IN ('T5C', 'MBL')` — the two Driven Brands corp types we receive (Take 5 + MBL). Add any further codes to every file's `IN (…)` clause if the scope widens.
- **Date window**: `invoiceDate >= DATEADD(month, -3, first_of_current_month)`. So if today is 2026-04-21, the window is **2026-01-01 through 2026-04-21** (current month + 3 prior months).
- **Voided invoices excluded** (`voided = 0`).

## How to run

Any of:

- **SSMS / Azure Data Studio** — open each `.sql`, run it, "Save Results As…" CSV with headers.
- **`sqlcmd` / `bcp`** — scriptable; recommend `bcp` with `-c -t,` for proper CSV.
- **Node / TS script** using the existing `sb-bridge` Drizzle client in [platform/layers/sb-bridge/server/db/](../../../../../platform/layers/sb-bridge/server/db/). Could be wrapped in a Nuxt server route later to support "customer downloads their own extract."

Drop the CSVs into [../../source-data/](../../source-data/). Naming must match the output file names above so the DuckDB loader picks them up.

## Why raw, not pre-aggregated

The aggregation (period buckets, fee rollups, reconciliation math) happens in DuckDB on top of the loaded CSVs. That way:

1. Re-slicing a different way doesn't require re-hitting MSSQL.
2. The extract pipeline stays identical for other Driven-Brands-style clients — swap the corpType filter and you're done.
3. The fee math is visible and auditable in one place (DuckDB queries) rather than buried in extract-side SQL.

## Open items

- **Store-number matching** — we keep `storeNumber`, `importStoreNumber`, `sapStoreNumber`, `aiStoreNumber` all at the site level, and `invoiceImportStoreNumber` at the invoice level. The reconciliation will need to pick which one Driven Brands uses as the join key. TBD once we see their side of the data.
- **AI fee dollar amount** — not persisted on the invoice row. Computed in DuckDB using the fee-config cascade (site → customer → brand) per the legacy `CalculateInvoiceFees.sql` logic.
