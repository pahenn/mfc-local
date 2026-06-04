# Driven Brands KPI ↔ SoundBilling Reconciliation — Analysis Notes

Working notes and conclusions for reconciling Driven Brands' **Fleet KPI Table Report**
against MFC **SoundBilling** invoice revenue. This is the methodology/decisions record;
the pipeline mechanics live in [README.md](./README.md), and the shareable summary is the
generated HTML report (see *Reproduce* below).

_Last updated: 2026-06-04 · first run against the **August 2025** window._

---

## What we were asked to do

Read the new-shape Fleet KPI xlsx, then find discrepancies between its store-level sales
and SoundBilling invoice data (`Invoice` / `InvoiceItemBridge`).

## Key gotcha: the KPI file's data window ≠ its filename date

`Fleet KPI Table Report - April 24, 2026.xlsx` actually contains **Aug 3–30, 2025** daily
data. The locally-extracted invoices were Jan–Apr 2026 (the extract uses a rolling
"current month + 3 prior" filter), so the first reconciliation produced **zero matches** —
disjoint time windows, not a bug.

**Fix:** re-extracted invoices for the matching window. Only `fleets` + `invoices` are
date-filtered; `sites` / `customers` / `corporation_types` are date-independent and were
reused. `v_invoice_enriched` does **not** need the 130MB `invoice_item_bridge`. The August
extract lives in `source-data-aug2025/` (invoices 65,353 rows, fleets 8,689); the build DB
is `db_aug2025.duckdb`. DB connection: `rds-mssql.api.myfleet.services / SoundBilling`
(FreeTDS, creds in `local/.env`).

> **Before reconciling any KPI file, check its real MIN/MAX date** and extract invoices for
> that window. To re-window, edit the date predicate in `queries/extract/04_fleets.sql` and
> `05_invoices.sql` (e.g. `Invoice_Date >= '2025-08-01' AND < '2025-09-01'`).

## The new file shape

| | Old (April 7 file) | **New (April 24 file)** |
|---|---|---|
| Sheets | 1 | **2: `Local` + `National`** |
| Columns | 17 (Region, COSC/FZ, product breakdown) | 9 |
| Grain | Weekly (`Week Ending`) | **Daily (`Date`)** |
| New metrics | — | **`Net Sales`, `Tickets`** |

Ingest for the new shape: [`scripts/driven_kpi_daily_xlsx_to_csv.py`](./scripts/driven_kpi_daily_xlsx_to_csv.py)
reads both sheets, tags each row with `segment` (`local`/`national`), and writes
`source-data/driven_brands_kpi_daily.csv`. The old weekly converter is untouched.

## The decisive finding: which MFC number to compare

Driven's **Net Sales** = gross − discounts, and **excludes sales tax**. The matching MFC
figure is the **pre-tax gross invoice**, *not* the post-prepayment balance:

| MFC figure | Definition | Verdict |
|---|---|---|
| `mfcTotalBalance` | `invoiceTotalAmount − prepaidTotalAmount` | **Wrong.** Reads $0 for prepaid fleets while the store rang real sales. Produced ~$960K of phantom variance. |
| `mfcGrossExTax` | `invoiceTotalAmount − invoiceTaxTotalAmount` | **Used.** Prepaid invoices still carry full gross, so they reconcile. Driven net is tax-exclusive, so we strip MFC tax to match. |

`reconVariance` / `reconStatus` in [`40_variance_daily.sql`](./queries/duckdb/40_variance_daily.sql)
run on `mfcGrossExTax − drivenNetSales`. The balance-based `varianceGross` / `varianceNet`
columns are retained for reference only.

Empirical proof — e.g. *OK Veterans Exemptions* store 706: balance `$0`, gross invoice
`$2,128` = Driven net `$2,128` exactly.

## Scope and filters

- **Grain.** Daily KPI rolled to the Saturday week-ending; invoices bucketed the same way.
  Join on `(weekEnding, fleetAccountNumber = FleetID, storeNumber)`. Voided invoices excluded.
- **Drop `missing_driven`.** MFC billed a (fleet, store, week) Driven didn't report → stores
  Driven doesn't own. Out of scope. We only balance stores Driven sends us.
- **Drop education / prepaid fleets** from amount-variance bins (universities, colleges, ISDs,
  student-faculty — run as prepaid programs that distort billed-amount variance). Flagged via
  `isEducationFleet` (name match on student/university/college/faculty). Four commercial
  businesses that merely contain a keyword are **kept**: `165229` College Hunks Hauling Junk,
  `158595` University Motors Nashville, `143229` University Rentals, `194954` White Knight Pest
  (College Stn = College Station, TX). Name matching is imperfect for acronym-only schools —
  revisit if a clean institution flag becomes available.

## Results (August 2025)

On the pre-tax-gross-vs-net basis, in-scope stores reconcile almost perfectly:

- **Matched** (within $1): local **$3,565,607** vs Driven **$3,565,600** (Δ **$7**) across 22,445
  rows; national **$920,846** vs **$920,846** (Δ **$0**).
- **Real amount variance** (both sides present, >$5 & >5%): only **137 local + 48 national** rows,
  ~$15.5K total. The original "scary" >5% bin ($1.98M local) was ~99% a metric artifact
  (comparing balance instead of pre-tax gross).
- The remaining >5% rows are small-dollar near-misses; a chunk is sales-tax handling
  (`varianceInvoiceVsNet` isolates the tax slice).

### `missing_mfc` — Driven sales MFC never invoiced (~$4.30M)

Not a billing-amount problem. Overwhelmingly **national fleet-management / leasing / rental
accounts billed centrally**, which never flow through per-store SoundBilling invoices:

| Driver | Driven net |
|---|---|
| national · standard (Enterprise, Element, LeasePlan, Hertz, ARI/Holman, Emkay, Merchants…) | ~$3.60M |
| local · standard (CarCare Promotions, etc. — possible intake / store-key gaps) | ~$0.62M |
| local · education / prepaid | ~$0.08M |

The **local standard** slice is the only part worth chasing as genuine intake or store-key gaps.

## Conclusions

1. SoundBilling and Driven **agree on revenue** for the stores Driven reports, once compared on
   the right basis (pre-tax gross invoice vs net sales).
2. The apparent multi-million-dollar variance was a **metric-selection artifact** (post-prepay
   balance), not a billing error.
3. The real open item is **coverage**, not amounts: ~$3.6M of national central-billing that MFC
   doesn't invoice per store (expected), plus a small local slice to investigate.

## Open items / next steps

- Segment the (out-of-scope) `missing_driven` rows via MFC's `Fleet_NationalAccount` flag if we
  ever want to characterize them.
- Confirm the sales-tax hypothesis on the residual >5% rows using `varianceInvoiceVsNet`.
- Investigate the **local · standard** `missing_mfc` accounts for intake / store-number key gaps.
- `30_variance.sql` (old weekly path) references `fleetAccountNumber`, which doesn't exist on
  `v_invoice_enriched` (it's `fleetID`) — latent bug; `40_variance_daily.sql` aliases it correctly.

## Reproduce

```bash
cd driven-brands-analytics

# 1. (one-time per window) extract invoices+fleets for the KPI's date window, then build the DB
#    — non-destructive: writes to source-data-aug2025/, reuses the date-independent dimensions.
duckdb db_aug2025.duckdb <<'SQL'
CREATE TABLE invoices AS SELECT * FROM read_csv_auto('source-data-aug2025/invoices.csv', sample_size=-1);
CREATE TABLE fleets   AS SELECT * FROM read_csv_auto('source-data-aug2025/fleets.csv', sample_size=-1);
CREATE TABLE sites             AS SELECT * FROM read_csv_auto('source-data/sites.csv', sample_size=-1);
CREATE TABLE customers         AS SELECT * FROM read_csv_auto('source-data/customers.csv', sample_size=-1);
CREATE TABLE corporation_types AS SELECT * FROM read_csv_auto('source-data/corporation_types.csv', sample_size=-1);
CREATE TABLE driven_brands_kpi_daily AS SELECT * FROM read_csv_auto('source-data/driven_brands_kpi_daily.csv', sample_size=-1);
SQL

# 2. build the views
duckdb db_aug2025.duckdb < queries/duckdb/10_reconciliation_view.sql
duckdb db_aug2025.duckdb < queries/duckdb/40_variance_daily.sql

# 3. inspect, or regenerate the HTML report
duckdb db_aug2025.duckdb -box "SELECT * FROM v_variance_daily_bins;"
./scripts/build_recon_report.py        # -> reports/reconciliation_aug2025.html
```

Key views in `40_variance_daily.sql`: `v_variance_daily_fleet_store_week` (raw, all statuses,
incl. `isEducationFleet`), `v_variance_daily_filtered` (in-scope balancing population),
`v_variance_daily_missing_mfc`, `v_variance_daily_bins`, `v_variance_daily_summary`,
`v_top_variances_daily`, `v_variance_daily_by_{store,fleet}`.
