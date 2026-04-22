-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: variance analysis (MFC vs Driven Brands side)
--
-- This is the CLI/batch mirror of the dashboard's "Reconciliation" tab —
-- both surfaces compute the same join over the same grain.
--
-- Inputs
--   • v_invoice_enriched   — MFC per-invoice, enriched with fleet/site/fee
--                            context. Built in 10_reconciliation_view.sql.
--   • driven_brands_kpi    — Driven Brands weekly KPI export (loaded from
--                            source-data/driven_brands_kpi.csv, produced by
--                            scripts/driven_kpi_xlsx_to_csv.py).
--
-- Grain
--   One row per (weekEnding, fleetAccountNumber, storeNumber).
--
--   • Driven's weekEnding is Saturday (US retail Sun–Sat week).
--   • MFC rows are bucketed to the Saturday that ends the week containing
--     invoiceDate: weekEnding = invoiceDate + (6 - date_part('dow', d))
--     (dow: 0=Sun … 6=Sat).
--
-- Key columns on the output row
--   mfcInvoiceCount      COUNT(DISTINCT invoiceID) on the MFC side
--   mfcTotalBalance      SUM(invoiceTotalAmount − prepaidTotalAmount) — what
--                        MFC collects, net of any prepayment offsets.
--   mfcTotalDiscount     SUM(invoiceTotalDiscounts)
--   drivenGrossSales     SUM(grossSales) from Driven's KPI row
--   drivenDiscounts      SUM(discountsDollars)
--   drivenCarsPerDay     SUM(carsPerDay)
--   drivenOilChanges     SUM(oilChanges)
--
--   variance             mfcTotalBalance − drivenGrossSales   (MFC minus Driven)
--   variancePct          variance / drivenGrossSales          (null when Driven = 0)
--   reconStatus          matched  | variance | missing_mfc | missing_driven
--                        matched: |variance| < $1.00
--                        missing_mfc:    MFC side has no invoices for this
--                                        (fleet, store, week) but Driven does
--                        missing_driven: Driven has no row but MFC does
-- ─────────────────────────────────────────────────────────────────────────

-- Safe to run even if driven_brands_kpi.csv hasn't been loaded yet — the
-- dashboard's view-bootstrap creates an empty stub. When unloaded, every MFC
-- row will be flagged `missing_driven`.
CREATE TABLE IF NOT EXISTS driven_brands_kpi (
    yearMonth            VARCHAR,
    date                 DATE,
    fleetAccountName     VARCHAR,
    fleetAccountNumber   INTEGER,
    region               VARCHAR,
    storeNumber          INTEGER,
    weekEnding           DATE,
    coscFz               VARCHAR,
    airFilters           INTEGER,
    cabinFilters         INTEGER,
    carsPerDay           INTEGER,
    coolant              INTEGER,
    discountsDollars     DOUBLE,
    grossSales           DOUBLE,
    oilChanges           INTEGER,
    wipers               INTEGER,
    differentialFluidPct DOUBLE
);

CREATE OR REPLACE VIEW v_variance_fleet_store_week AS
WITH mfc AS (
    SELECT
        CAST(invoiceDate AS DATE)
          + (6 - date_part('dow', CAST(invoiceDate AS DATE)))::INTEGER AS weekEnding,
        fleetAccountNumber,
        MAX(fleetName)             AS fleetName,
        storeNumber,
        MAX(siteName)              AS siteName,
        COUNT(DISTINCT invoiceID)  AS invoiceCount,
        SUM(invoiceTotalAmount)    AS mfcTotalInvoice,
        SUM(mfcBalance)            AS mfcTotalBalance,
        SUM(invoiceTotalDiscounts) AS mfcTotalDiscount
    FROM v_invoice_enriched
    WHERE COALESCE(voided, 0) = 0
    GROUP BY 1, fleetAccountNumber, storeNumber
),
drv AS (
    SELECT
        CAST(weekEnding AS DATE)                  AS weekEnding,
        TRY_CAST(fleetAccountNumber AS INTEGER)   AS fleetAccountNumber,
        MAX(fleetAccountName)                     AS fleetAccountName,
        TRY_CAST(storeNumber AS INTEGER)          AS storeNumber,
        SUM(TRY_CAST(grossSales AS DOUBLE))       AS drivenGrossSales,
        SUM(TRY_CAST(discountsDollars AS DOUBLE)) AS drivenDiscounts,
        SUM(TRY_CAST(carsPerDay AS INTEGER))      AS drivenCarsPerDay,
        SUM(TRY_CAST(oilChanges AS INTEGER))      AS drivenOilChanges
    FROM driven_brands_kpi
    GROUP BY 1, TRY_CAST(fleetAccountNumber AS INTEGER), TRY_CAST(storeNumber AS INTEGER)
)
SELECT
    COALESCE(m.weekEnding, d.weekEnding)                   AS weekEnding,
    COALESCE(m.fleetAccountNumber, d.fleetAccountNumber)   AS fleetAccountNumber,
    COALESCE(m.fleetName, d.fleetAccountName, '<unknown>') AS fleetName,
    COALESCE(m.storeNumber, d.storeNumber)                 AS storeNumber,
    COALESCE(m.siteName, '<unknown>')                      AS siteName,

    m.invoiceCount     AS mfcInvoiceCount,
    m.mfcTotalInvoice,
    m.mfcTotalBalance,
    m.mfcTotalDiscount,

    d.drivenGrossSales,
    d.drivenDiscounts,
    d.drivenCarsPerDay,
    d.drivenOilChanges,

    COALESCE(m.mfcTotalBalance, 0) - COALESCE(d.drivenGrossSales, 0) AS variance,
    CASE WHEN d.drivenGrossSales > 0
         THEN (COALESCE(m.mfcTotalBalance, 0) - d.drivenGrossSales) / d.drivenGrossSales
         ELSE NULL END AS variancePct,

    CASE
        WHEN m.mfcTotalBalance IS NULL                         THEN 'missing_mfc'
        WHEN d.drivenGrossSales IS NULL                        THEN 'missing_driven'
        WHEN abs(COALESCE(m.mfcTotalBalance,0)
               - COALESCE(d.drivenGrossSales,0)) < 1.00        THEN 'matched'
        ELSE 'variance'
    END AS reconStatus
FROM mfc m
FULL OUTER JOIN drv d
  ON d.weekEnding         = m.weekEnding
 AND d.fleetAccountNumber = m.fleetAccountNumber
 AND d.storeNumber        = m.storeNumber;


-- The headline numbers — one row per status bucket.
CREATE OR REPLACE VIEW v_variance_summary AS
SELECT
    reconStatus,
    COUNT(*)                         AS rows,
    SUM(COALESCE(mfcInvoiceCount,0)) AS mfcInvoices,
    SUM(COALESCE(mfcTotalBalance,0)) AS mfcTotal,
    SUM(COALESCE(drivenGrossSales,0)) AS drivenTotal,
    SUM(COALESCE(variance,0))        AS netVariance
FROM v_variance_fleet_store_week
GROUP BY reconStatus
ORDER BY reconStatus;


-- Top 50 largest absolute variances — "where to look first"
CREATE OR REPLACE VIEW v_top_variances AS
SELECT *
FROM v_variance_fleet_store_week
WHERE reconStatus = 'variance'
ORDER BY abs(variance) DESC
LIMIT 50;


-- Is this shop-driven or fleet-driven? Roll up to each dimension separately.
CREATE OR REPLACE VIEW v_variance_by_store AS
SELECT
    storeNumber,
    siteName,
    COUNT(DISTINCT weekEnding || '|' || fleetAccountNumber) AS fleetWeeksTouched,
    SUM(variance)                                           AS netVariance,
    SUM(abs(variance))                                      AS absVariance
FROM v_variance_fleet_store_week
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;

CREATE OR REPLACE VIEW v_variance_by_fleet AS
SELECT
    fleetAccountNumber,
    fleetName,
    COUNT(DISTINCT weekEnding || '|' || storeNumber) AS storeWeeksTouched,
    SUM(variance)                                    AS netVariance,
    SUM(abs(variance))                               AS absVariance
FROM v_variance_fleet_store_week
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;
