-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: variance analysis — SoundBilling invoices vs Driven Brands
--          *new-shape* daily KPI export (Local + National).
--
-- Sibling of 30_variance.sql. That file reconciles the OLD weekly KPI export
-- (driven_brands_kpi). This file reconciles the NEW daily two-sheet export
-- (driven_brands_kpi_daily, produced by scripts/driven_kpi_daily_xlsx_to_csv.py).
--
-- Inputs
--   • v_invoice_enriched      — MFC/SoundBilling per-invoice, enriched with
--                               fleet/site/fee context. Built in
--                               10_reconciliation_view.sql.
--   • driven_brands_kpi_daily — daily KPI rows, one per (segment, date, fleet,
--                               store), loaded from source-data/driven_brands_kpi_daily.csv.
--
-- Grain
--   One row per (weekEnding, segment, fleetAccountNumber, storeNumber).
--   The KPI side is DAILY, so we roll it up to the Saturday that ends the week
--   containing each `date`, matching how the SoundBilling side is bucketed:
--     weekEnding = d + (6 - date_part('dow', d))   (dow: 0=Sun … 6=Sat)
--
-- WHICH MFC NUMBER TO COMPARE  (learned empirically, Aug-2025 data)
--   Driven's "Net Sales" = gross − discounts, and EXCLUDES sales tax. The
--   matching MFC figure is therefore the PRE-TAX GROSS INVOICE, not the
--   post-prepayment balance:
--     • mfcTotalBalance  = invoiceTotalAmount − prepaidTotalAmount
--                          → wrong for prepaid fleets (balance = $0 while the
--                            store rang real sales). This produced ~$960K of
--                            phantom variance in Aug 2025.
--     • mfcGrossExTax    = invoiceTotalAmount − invoiceTaxTotalAmount
--                          → the basis used for reconVariance / reconStatus.
--                            Prepaid invoices still carry their full gross, so
--                            they reconcile.
--   The balance-based varianceGross / varianceNet columns are kept for
--   reference / back-compat with 30_variance.sql, but are NOT the headline.
-- ─────────────────────────────────────────────────────────────────────────

-- Safe to run even if the daily CSV hasn't been loaded — create an empty stub
-- so the views compile. When unloaded, every SoundBilling row is missing_driven.
CREATE TABLE IF NOT EXISTS driven_brands_kpi_daily (
    segment            VARCHAR,
    date               DATE,
    fleetAccountName   VARCHAR,
    fleetAccountNumber INTEGER,
    storeNumber        INTEGER,
    carsPerDay         INTEGER,
    discountsDollars   DOUBLE,
    grossSales         DOUBLE,
    netSales           DOUBLE,
    tickets            INTEGER
);

CREATE OR REPLACE VIEW v_variance_daily_fleet_store_week AS
WITH mfc AS (
    SELECT
        CAST(invoiceDate AS DATE)
          + (6 - date_part('dow', CAST(invoiceDate AS DATE)))::INTEGER AS weekEnding,
        fleetID                    AS fleetAccountNumber,  -- README: fleetAccountNumber = FleetID
        MAX(fleetName)             AS fleetName,
        storeNumber,
        MAX(siteName)              AS siteName,
        COUNT(DISTINCT invoiceID)  AS invoiceCount,
        SUM(invoiceTotalAmount)    AS mfcTotalInvoice,
        SUM(invoiceTaxTotalAmount) AS mfcTotalTax,
        SUM(mfcBalance)            AS mfcTotalBalance,
        SUM(invoiceTotalDiscounts) AS mfcTotalDiscount
    FROM v_invoice_enriched
    WHERE COALESCE(voided, 0) = 0
    GROUP BY 1, fleetID, storeNumber
),
drv AS (
    SELECT
        CAST(date AS DATE)
          + (6 - date_part('dow', CAST(date AS DATE)))::INTEGER  AS weekEnding,
        segment,
        TRY_CAST(fleetAccountNumber AS INTEGER)   AS fleetAccountNumber,
        MAX(fleetAccountName)                     AS fleetAccountName,
        TRY_CAST(storeNumber AS INTEGER)          AS storeNumber,
        SUM(TRY_CAST(grossSales AS DOUBLE))       AS drivenGrossSales,
        SUM(TRY_CAST(netSales AS DOUBLE))         AS drivenNetSales,
        SUM(TRY_CAST(discountsDollars AS DOUBLE)) AS drivenDiscounts,
        SUM(TRY_CAST(carsPerDay AS INTEGER))      AS drivenCarsPerDay,
        SUM(TRY_CAST(tickets AS INTEGER))         AS drivenTickets
    FROM driven_brands_kpi_daily
    GROUP BY 1, segment,
             TRY_CAST(fleetAccountNumber AS INTEGER),
             TRY_CAST(storeNumber AS INTEGER)
),
joined AS (
SELECT
    COALESCE(m.weekEnding, d.weekEnding)                   AS weekEnding,
    d.segment,
    COALESCE(m.fleetAccountNumber, d.fleetAccountNumber)   AS fleetAccountNumber,
    COALESCE(m.fleetName, d.fleetAccountName, '<unknown>') AS fleetName,
    COALESCE(m.storeNumber, d.storeNumber)                 AS storeNumber,
    COALESCE(m.siteName, '<unknown>')                      AS siteName,

    m.invoiceCount     AS mfcInvoiceCount,
    m.mfcTotalInvoice,                                       -- gross invoice (incl tax)
    m.mfcTotalTax,
    (m.mfcTotalInvoice - m.mfcTotalTax) AS mfcGrossExTax,    -- MFC basis used below
    m.mfcTotalBalance,                                       -- post-prepayment (reference)
    m.mfcTotalDiscount,

    d.drivenGrossSales,
    d.drivenNetSales,
    d.drivenDiscounts,
    d.drivenCarsPerDay,
    d.drivenTickets,

    -- ── Primary comparison: MFC pre-tax gross invoice vs Driven net sales ──
    COALESCE(m.mfcTotalInvoice - m.mfcTotalTax, 0)
      - COALESCE(d.drivenNetSales, 0)                       AS reconVariance,
    CASE WHEN d.drivenNetSales > 0
         THEN (COALESCE(m.mfcTotalInvoice - m.mfcTotalTax, 0) - d.drivenNetSales)
              / d.drivenNetSales
         ELSE NULL END                                      AS reconVariancePct,

    -- ── Reference variances (vs post-prepayment balance — see header) ──
    COALESCE(m.mfcTotalBalance, 0) - COALESCE(d.drivenGrossSales, 0) AS varianceGross,
    COALESCE(m.mfcTotalBalance, 0) - COALESCE(d.drivenNetSales, 0)   AS varianceNet,
    -- gross invoice WITH tax vs net — isolates how much of the residual is tax
    COALESCE(m.mfcTotalInvoice, 0) - COALESCE(d.drivenNetSales, 0)   AS varianceInvoiceVsNet,

    CASE
        WHEN m.mfcTotalInvoice IS NULL                        THEN 'missing_mfc'
        WHEN d.drivenNetSales  IS NULL                        THEN 'missing_driven'
        WHEN abs(COALESCE(m.mfcTotalInvoice - m.mfcTotalTax, 0)
               - COALESCE(d.drivenNetSales, 0)) < 1.00        THEN 'matched'
        ELSE 'variance'
    END AS reconStatus
FROM mfc m
FULL OUTER JOIN drv d
  ON d.weekEnding         = m.weekEnding
 AND d.fleetAccountNumber = m.fleetAccountNumber
 AND d.storeNumber        = m.storeNumber
)
SELECT
    *,
    -- Education institutions (universities / colleges / ISDs / student-faculty)
    -- run as prepaid programs; flagged so analysis can split them out. The four
    -- excluded fleetIDs are commercial businesses that merely contain an
    -- education keyword:
    --   165229 College Hunks Hauling Junk · 158595 University Motors Nashville
    --   143229 University Rentals         · 194954 White Knight Pest (College Stn, TX)
    ((lower(fleetName) LIKE '%student%'
   OR lower(fleetName) LIKE '%universit%'
   OR lower(fleetName) LIKE '%college%'
   OR lower(fleetName) LIKE '%faculty%')
   AND fleetAccountNumber NOT IN (165229, 158595, 143229, 194954)) AS isEducationFleet
FROM joined;


-- ─────────────────────────────────────────────────────────────────────────
-- Balancing population: stores Driven actually reports AND MFC invoices —
-- i.e. both sides present (matched + variance), education fleets removed.
--   • missing_driven dropped: MFC billed a (fleet, store, week) Driven didn't
--     report — stores Driven doesn't own. Out of scope.
--   • missing_mfc kept OUT of this view (see v_variance_daily_missing_mfc) —
--     no MFC invoice means no amount to bin.
--   • education/prepaid fleets removed — they distort billed-amount variance.
-- ─────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_variance_daily_filtered AS
SELECT *
FROM v_variance_daily_fleet_store_week
WHERE reconStatus IN ('matched', 'variance')
  AND NOT isEducationFleet;


-- Driven rang sales but MFC issued no invoice for that (fleet, store, week).
-- Mostly nationally/centrally-billed fleet & leasing accounts that don't flow
-- through per-store SoundBilling invoices; a small education/prepaid slice.
CREATE OR REPLACE VIEW v_variance_daily_missing_mfc AS
SELECT segment, fleetAccountNumber, fleetName, storeNumber, weekEnding,
       drivenNetSales, drivenGrossSales, isEducationFleet
FROM v_variance_daily_fleet_store_week
WHERE reconStatus = 'missing_mfc';


-- ─────────────────────────────────────────────────────────────────────────
-- Variance-% bins on the primary basis (pre-tax gross invoice vs Driven net),
-- segmented. A $5 absolute floor folds tiny-ticket rounding into the good bin
-- so the counts reflect real money, not a $1 gap on a $20 oil change.
-- ─────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_variance_daily_bins AS
SELECT
    segment,
    CASE
        WHEN abs(reconVariance) < 5            THEN '1) <=2% or <$5'
        WHEN abs(reconVariancePct) <= 0.02     THEN '1) <=2% or <$5'
        WHEN abs(reconVariancePct) <= 0.05     THEN '2) >2% to <=5%'
        ELSE '3) >5%'
    END                                AS bin,
    COUNT(*)                           AS rows,
    ROUND(SUM(abs(reconVariance)), 0)  AS absVarianceUSD
FROM v_variance_daily_filtered
WHERE reconVariancePct IS NOT NULL
GROUP BY segment, bin
ORDER BY segment, bin;


-- The headline numbers — one row per (segment, status) bucket.
CREATE OR REPLACE VIEW v_variance_daily_summary AS
SELECT
    COALESCE(segment, '<mfc-only>')   AS segment,
    reconStatus,
    COUNT(*)                          AS rows,
    SUM(COALESCE(mfcInvoiceCount,0))  AS mfcInvoices,
    SUM(COALESCE(mfcGrossExTax,0))    AS mfcGrossExTax,
    SUM(COALESCE(drivenNetSales,0))   AS drivenNet,
    SUM(COALESCE(reconVariance,0))    AS netVariance
FROM v_variance_daily_fleet_store_week
GROUP BY 1, reconStatus
ORDER BY 1, reconStatus;


-- Top 50 largest absolute variances (both sides present) — "where to look first"
CREATE OR REPLACE VIEW v_top_variances_daily AS
SELECT *
FROM v_variance_daily_filtered
WHERE reconStatus = 'variance'
ORDER BY abs(reconVariance) DESC
LIMIT 50;


-- Is this shop-driven or fleet-driven? Roll up to each dimension separately.
CREATE OR REPLACE VIEW v_variance_daily_by_store AS
SELECT
    storeNumber,
    siteName,
    COUNT(DISTINCT weekEnding || '|' || fleetAccountNumber) AS fleetWeeksTouched,
    SUM(reconVariance)                                      AS netVariance,
    SUM(abs(reconVariance))                                 AS absVariance
FROM v_variance_daily_filtered
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;

CREATE OR REPLACE VIEW v_variance_daily_by_fleet AS
SELECT
    fleetAccountNumber,
    fleetName,
    COUNT(DISTINCT weekEnding || '|' || storeNumber) AS storeWeeksTouched,
    SUM(reconVariance)                               AS netVariance,
    SUM(abs(reconVariance))                          AS absVariance
FROM v_variance_daily_filtered
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;
