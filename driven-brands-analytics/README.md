# Driven Brands Analytics

Reconciliation tooling for comparing **MFC's view** of Driven Brands revenue against **Driven Brands' own view**, at the (fleet customer × store × week-ending) grain.

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
  driven-data/            # drop Driven Brands xlsx exports here (Fleet KPI Table Report, etc.)
  source-data/            # CSVs consumed by the dashboard + DuckDB loader
  scripts/
    run_extracts.sh                # runs the six MSSQL extracts
    driven_kpi_xlsx_to_csv.py      # converts Fleet KPI xlsx → source-data/driven_brands_kpi.csv
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

One row per `(period, fleetCode, storeNumber)`. Columns:

| Column | Source |
|---|---|
| `period` | `date_trunc('month', invoiceDate)` |
| `fleetCode`, `fleetAccountNumber`, `fleetAccountName` | `Fleet.fleetCode` (combined prefix-number), `Fleet.fleetID` (numeric), `Fleet.fleetCompanyName` (name) — renamed to match Driven Brands' KPI export shape |
| `storeNumber`, `siteName` | `CustomerSite.storeNumber`, `CustomerSite.siteName` |
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

## Variance / Reconciliation

The variance layer compares **MFC's per-invoice balance** against **Driven Brands' weekly KPI export** at the `(weekEnding, fleetAccountNumber, storeNumber)` grain. Two surfaces run the same logic:

- **SQL file**: [`queries/duckdb/30_variance.sql`](./queries/duckdb/30_variance.sql) — batch/CLI variant, produces `v_variance_fleet_store_week` plus summary / drilldown rollups.
- **Dashboard tab**: the "Reconciliation" tab in [`dashboard.html`](./dashboard.html) — interactive variant, same join executed inline as a CTE so it respects the FilterBar predicates.

### Inputs

| Source | Table | Grain | Origin |
|---|---|---|---|
| MFC | `v_invoice_enriched` | per-invoice | Built from the six MSSQL extracts via [`10_reconciliation_view.sql`](./queries/duckdb/10_reconciliation_view.sql) (dashboard builds the same view in-page). |
| Driven | `driven_brands_kpi` | weekly per (fleet, store) | Produced by [`scripts/driven_kpi_xlsx_to_csv.py`](./scripts/driven_kpi_xlsx_to_csv.py) from the Fleet KPI Table Report xlsx dropped in `driven-data/`, loaded from `source-data/driven_brands_kpi.csv`. |

### Grain: Saturday week-ending

Driven's `weekEnding` is a Saturday (US retail Sun–Sat week). MFC rows are bucketed to the same week using:

```sql
weekEnding = CAST(invoiceDate AS DATE)
           + (6 - date_part('dow', CAST(invoiceDate AS DATE)))::INTEGER
```

`date_part('dow', d)` returns `0 = Sunday … 6 = Saturday`, so the expression advances any date forward to the Saturday that ends its week.

Example: `invoiceDate = 2025-12-28` (Sunday) and `invoiceDate = 2026-01-03` (Saturday) both map to `weekEnding = 2026-01-03`, which lines up with the Driven row for the same week.

### Join keys

```
mfc.weekEnding         = drv.weekEnding
mfc.fleetAccountNumber = drv.fleetAccountNumber
mfc.storeNumber        = drv.storeNumber
```

A `FULL OUTER JOIN` is used so rows present on only one side (a store that rang sales but MFC hasn't billed, or an MFC invoice against a store Driven didn't report) still surface with a status flag rather than being dropped.

`fleetAccountNumber` is the numeric portion of MFC's `fleetCode` (`MBL-176772` → `176772`), which is also the `FleetID` primary key. It matches Driven's "Fleet Account #" directly.

### Output row

| Column | Definition |
|---|---|
| `weekEnding` | Saturday of the week (from either side — they're equal when the row matches) |
| `fleetAccountNumber`, `fleetName`, `storeNumber`, `siteName` | Identity keys for the bucket (with `<unknown>` placeholders for Driven-only rows where MFC has no matching fleet/site) |
| `mfcInvoiceCount` | `COUNT(DISTINCT invoiceID)` on the MFC side |
| `mfcTotalInvoice` | `SUM(invoiceTotalAmount)` |
| `mfcTotalBalance` | `SUM(invoiceTotalAmount − prepaidTotalAmount)` — **the number compared against Driven** |
| `mfcTotalDiscount` | `SUM(invoiceTotalDiscounts)` |
| `drivenGrossSales` | `SUM(grossSales)` from Driven's KPI rows |
| `drivenDiscounts` | `SUM(discountsDollars)` |
| `drivenCarsPerDay`, `drivenOilChanges` | Volume signals, useful as sanity checks |
| `variance` | `mfcTotalBalance − drivenGrossSales` (signed; MFC minus Driven) |
| `variancePct` | `variance / drivenGrossSales`, `NULL` when `drivenGrossSales = 0` |
| `reconStatus` | one of `matched` / `variance` / `missing_mfc` / `missing_driven` (see below) |

### Status buckets

| Status | Condition | Interpretation |
|---|---|---|
| `matched` | `abs(mfcTotalBalance − drivenGrossSales) < 1.00` | Both sides reconcile within $1.00 (rounding tolerance). |
| `variance` | Both sides present, but \|difference\| ≥ $1.00 | The row is the main target — something billed differently than the store sold. |
| `missing_mfc` | MFC side is `NULL` | Driven reports activity but MFC has no invoice for that (fleet, store, week). Either missed intake or misfiled elsewhere. |
| `missing_driven` | Driven side is `NULL` | MFC billed but Driven's export has no matching row. Either a mismatched key or activity Driven didn't include. |

### CLI (SQL file) surface

[`30_variance.sql`](./queries/duckdb/30_variance.sql) creates these views when run against a DuckDB containing the extracts:

| View | Contents |
|---|---|
| `v_variance_fleet_store_week` | The main row — one per `(weekEnding, fleetAccountNumber, storeNumber)` with all the columns above. |
| `v_variance_summary` | One row per `reconStatus` with counts, MFC total, Driven total, net variance. The headline. |
| `v_top_variances` | 50 largest absolute variances — "where to look first." |
| `v_variance_by_store` | Store-level rollup of variance rows — answers "is this a shop problem?" |
| `v_variance_by_fleet` | Fleet-level rollup — answers "is this a fleet problem?" |

The SQL-file path filters voided invoices out on the MFC side (`WHERE COALESCE(voided,0) = 0`) but does not accept other parameters; all filtering is downstream on the view.

### Dashboard tab surface

Under the hood the tab builds the same CTE (`mfc` + `drv`) and the same FULL OUTER JOIN, but wraps each side's aggregation in the current FilterBar predicates. Results are paged (top 1,000 rows display, full set on CSV download).

**Filter → side mapping:**

| FilterBar control | MFC side | Driven side |
|---|---|---|
| Date range (`startDate`, `endDate`) | Applied to `invoiceDate` | Applied to `weekEnding` |
| Fleet (dropdown) | `fleetAccountNumber = N` | `fleetAccountNumber = N` |
| Store (dropdown) | `storeNumber = N` | `storeNumber = N` |
| Region / District | Applied — MFC-side only (Driven has no equivalent) | — |
| Voided | `exclude` / `include` / `only` on MFC `voided` flag | — (Driven has no concept of voided) |
| Search | Matches fleet #, fleet name, store #, site name on MFC | — |

**Tab-local controls:**

- **Status** dropdown — filters the displayed rows to one of `all` / `variance only` / `matched only` / `missing from MFC` / `missing from Driven`. Summary counts in the caption always show all buckets regardless of the filter.
- **Sort** dropdown — `absVariance` (default, largest absolute first), `variance` (signed desc), `mfcTotal`, `drivenGross`, `weekEnding`.
- **Download CSV** — dumps the full filtered set (bypasses the 1,000-row display cap) with all columns.

**Totals row** in the table header sums `invoiceCount`, `mfcTotalBalance`, `drivenGrossSales`, `variance`, and `drivenCarsPerDay` across the entire filtered set — not just the visible page. Variance % is intentionally blank in the totals row (a ratio can't be meaningfully aggregated).

**Empty state**: if `driven_brands_kpi.csv` has zero rows (never loaded), the tab shows a banner pointing to the xlsx converter script rather than a table of all-null Driven columns. The "has KPI data" check uses an actual `COUNT(*)` rather than table existence, because the stub `CREATE TABLE IF NOT EXISTS driven_brands_kpi (…)` always exists so the views compile.

### Known sources of drift

- **Week-boundary math** — the formula above assumes Sun–Sat US retail weeks. If Driven ever ships a different boundary (Mon-start, fiscal week, etc.), the single place to update is `mfcWeekEndingExpr` in the dashboard and the `weekEnding` expression in `30_variance.sql`.
- **Voided invoices** — the SQL-file path hard-excludes voided; the dashboard lets the user toggle. If you reconcile from the CLI and the dashboard and get different numbers, the voided toggle is usually why.
- **Factored / non-invoice revenue** — `mfcTotalBalance` is post-prepayment. If a transaction is prepaid outside the invoice flow, Driven may still rank it as gross sales while MFC shows zero balance. Those rows land in `missing_mfc` or appear as pure-negative variance.
- **Fleet number mismatch** — Driven's `Fleet Account #` is always the numeric id; MFC's `fleetCode` carries a `MBL-` / `T5C-` / `AIN-` / `AIC-` prefix that we strip (`fleetAccountNumber = FleetID`). If a legacy invoice has an invalid/zero `fleetID`, it won't match anything on the Driven side.

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
4. **Variance layer** — client-specific shape for the external data and the join keys. The current `30_variance.sql` / dashboard "Reconciliation" tab are both wired to Driven Brands' weekly KPI export (fleet × store × week-ending). For a different partner, the pattern stays the same — only the Driven-side CTE (columns, grain, week-boundary math) changes.

Once the shape is stable, this becomes a download endpoint in the MFC platform: client authenticates, clicks "refresh my data," and gets a zip of the six CSVs plus a pre-built DuckDB file (or an HTML dashboard like `sales-dashboard/` with the data baked in).

## Open items

- **Store-number match key** — confirmed: Driven uses the same integer store number MFC derives from `CustomerSite.storeNumber` (stripping the `T5C` prefix and any `828` suffix). The other three site-level candidates (`importStoreNumber`, `sapStoreNumber`, `aiStoreNumber`) plus invoice-level `invoiceImportStoreNumber` are kept in the extract but not currently used in the variance join.
- **AI fee formula** — the DuckDB implementation is a simplified flat-plus-pct cascade. The legacy stored proc adds minimum-floor and override-table logic. Validate against a handful of known invoices before trusting the number, then tighten if needed.
- **`MBL` meaning** — flagged in the brand scope. Confirm which Driven Brands subsidiary this maps to so we label it right in outputs.
- **Variance tolerance** — `matched` is currently `|Δ| < $1.00`. Once we've seen real data for a few weeks, revisit whether this should be a percentage band or a per-fleet tolerance.
