# Driven Brands Analytics

Reconciliation tooling for comparing **MFC's view** of Driven Brands revenue against **Driven Brands' own view**, at the (fleet customer × T5 store × month) grain.

Scope: `corpType IN ('T5C', 'MBL')` — the two Driven Brands corp types we process.

Window: current calendar month + the three prior months (rolling).

## Directory layout

```
driven-brands-analytics/
  queries/
    extract/              # MSSQL — raw table dumps, run against the MFC legacy DB
      01_corporation_types.sql
      02_customers.sql
      03_customer_sites.sql
      04_fleets.sql
      05_invoices.sql
      06_invoice_item_bridge.sql
      README.md           # how to run + output filename contract
    duckdb/               # DuckDB — run on top of the loaded CSVs
      00_load.sql         # creates tables from CSVs in source-data/
      10_reconciliation_view.sql  # fleet × store × month view
      20_product_breakdown.sql    # SKU / service-type breakdown for drilldown
      30_variance.sql     # template for MFC vs Driven Brands comparison
  source-data/            # analysts drop the 6 CSV extracts here
  scripts/                # helpers (empty for now)
```

## The pipeline

```
MSSQL (MFC legacy)          CSVs                   DuckDB                    Analysis
─────────────────────       ──────────────         ──────────────            ──────────────
  extract/*.sql      ─▶     source-data/  ─▶       duckdb/00_load.sql  ─▶    duckdb/10,20,30
```

Two stages on purpose:

1. **Extract is dumb** — raw rows, no fee math, no rollups. Re-slicing later never touches MSSQL again.
2. **Reconciliation / fee math lives in DuckDB** — auditable, editable, iterable without re-extracting.

## The target reconciliation row

One row per `(period, fleetCode, t5StoreNumber)`. Columns:

| Column | Source |
|---|---|
| `period` | `date_trunc('month', invoiceDate)` |
| `fleetCode`, `fleetName` | `Fleet.fleetCode`, `Fleet.fleetCompanyName` |
| `t5StoreNumber`, `siteName` | `CustomerSite.storeNumber`, `CustomerSite.siteName` |
| `invoiceCount` | `COUNT(DISTINCT invoiceID)` |
| `totalInvoice` | `SUM(invoiceTotalAmount)` |
| `mfcTotalBalance` | `SUM(invoiceTotalAmount − prepaidTotalAmount)` — "what came through MFC" |
| `totalTax` | `SUM(invoiceTaxTotalAmount)` |
| `totalDiscount` | `SUM(invoiceTotalDiscounts)` |
| `totalCcFee` | `SUM(invoiceCCFees)` |
| `totalMfcFee` | `invoiceInvoiceFee` — single column |
| `totalAiFee` | AI fee computed via site → customer → brand cascade |
| `firstInvoiceDate`, `lastInvoiceDate` | Window edges per group |

Fee definitions documented inline in [`queries/duckdb/10_reconciliation_view.sql`](./queries/duckdb/10_reconciliation_view.sql).

## End-to-end usage

```bash
# 0. One-time setup (macOS): install ODBC + FreeTDS, then verify
brew install unixodbc freetds
../_utilities/sql-server/check_odbc.py

# Create local/.env with DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD.
# See ../_utilities/sql-server/README.md for the full format.

# 1. Run all six extracts (streams each result to source-data/*.csv)
./scripts/run_extracts.sh

# 2. Load + run the reconciliation views
duckdb db.duckdb < queries/duckdb/00_load.sql
duckdb db.duckdb < queries/duckdb/10_reconciliation_view.sql
duckdb db.duckdb < queries/duckdb/20_product_breakdown.sql
duckdb db.duckdb < queries/duckdb/30_variance.sql   # safe to run without Driven Brands side
```

## The generic-tool angle

This pipeline generalizes. For any client that needs the same kind of reconciliation:

1. **Extract templates** — swap the `corpType IN (…)` filter and window. Same query bodies.
2. **DuckDB load** — identical (same CSV filenames).
3. **Reconciliation view** — same SQL, unless the client uses a different definition of "balance" or "fee." If so, that diff lives in one place.
4. **Variance layer** — client-specific: their expected-revenue file, their join keys. `30_variance.sql` is a template.

Once the shape is stable, this becomes a download endpoint in the MFC platform: client authenticates, clicks "refresh my data," and gets a zip of the six CSVs plus a pre-built DuckDB file (or an HTML dashboard like `sales-dashboard/` with the data baked in).

## Open items

- **Store-number match key** — we keep four store-number columns on sites + one on invoice. Which one Driven Brands uses in their extract determines the join key for the variance step. Confirm once we see their format.
- **AI fee formula** — the DuckDB implementation is a simplified flat-plus-pct cascade. The legacy stored proc adds minimum-floor and override-table logic. Validate against a handful of known invoices before trusting the number, then tighten if needed.
- **`MBL` meaning** — flagged in the brand scope. Confirm which Driven Brands subsidiary this maps to so we label it right in outputs.
