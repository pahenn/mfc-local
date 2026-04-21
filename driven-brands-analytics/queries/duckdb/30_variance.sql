-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: variance analysis (MFC vs Driven Brands side)
-- Template — runs once you load a 'driven_brands_expected' table from the
-- Driven Brands side. Format assumed:
--
--   driven_brands_expected (
--     period           DATE,        -- first day of month
--     t5StoreNumber    VARCHAR,
--     fleetCode        VARCHAR,
--     expectedRevenue  DECIMAL
--   )
--
-- Adjust column names to whatever Driven Brands actually ships.
--
-- Safe to run without the Driven Brands side: if `driven_brands_expected`
-- hasn't been loaded yet, we create an empty shell so every MFC row gets
-- flagged `missing_from_driven`. Replace with the real load once it lands.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS driven_brands_expected (
    period           DATE,
    t5StoreNumber    INTEGER,
    fleetCode        VARCHAR,
    expectedRevenue  DECIMAL(19,4)
);

-- Side-by-side reconciliation. FULL OUTER JOIN so rows only in one side show up.
CREATE OR REPLACE VIEW v_variance_fleet_store_month AS
SELECT
    COALESCE(m.period,         d.period)         AS period,
    COALESCE(m.fleetCode,      d.fleetCode)      AS fleetCode,
    COALESCE(m.fleetName,      '<unknown>')      AS fleetName,
    COALESCE(m.t5StoreNumber,  d.t5StoreNumber)  AS t5StoreNumber,
    COALESCE(m.siteName,       '<unknown>')      AS siteName,

    m.totalInvoice        AS mfcTotalInvoice,
    m.mfcTotalBalance     AS mfcTotalBalance,
    d.expectedRevenue     AS drivenBrandsExpected,

    -- Raw variance
    COALESCE(m.mfcTotalBalance, 0) - COALESCE(d.expectedRevenue, 0)      AS variance,
    -- Signed % variance (pct of Driven Brands side; null if DB side is 0)
    CASE WHEN d.expectedRevenue > 0
         THEN (COALESCE(m.mfcTotalBalance, 0) - d.expectedRevenue) / d.expectedRevenue
         ELSE NULL
    END AS variancePct,

    -- "Where did this come from?" flags
    CASE
        WHEN m.mfcTotalBalance IS NULL           THEN 'missing_from_mfc'
        WHEN d.expectedRevenue IS NULL           THEN 'missing_from_driven'
        WHEN abs(m.mfcTotalBalance - d.expectedRevenue) < 1.00 THEN 'matched'
        ELSE 'variance'
    END AS reconStatus,

    m.invoiceCount        AS mfcInvoiceCount
FROM v_fleet_store_month m
FULL OUTER JOIN driven_brands_expected d
  ON d.period        = m.period
 AND d.fleetCode     = m.fleetCode
 AND d.t5StoreNumber = m.t5StoreNumber;

-- The headline numbers execs actually read
CREATE OR REPLACE VIEW v_variance_summary AS
SELECT
    reconStatus,
    COUNT(*)                         AS rows,
    SUM(mfcTotalBalance)             AS mfcTotal,
    SUM(drivenBrandsExpected)        AS drivenBrandsTotal,
    SUM(variance)                    AS netVariance
FROM v_variance_fleet_store_month
GROUP BY reconStatus
ORDER BY reconStatus;

-- Top 50 largest absolute variances — "where to look first"
CREATE OR REPLACE VIEW v_top_variances AS
SELECT *
FROM v_variance_fleet_store_month
WHERE reconStatus = 'variance'
ORDER BY abs(variance) DESC
LIMIT 50;

-- Is this shop-driven or fleet-driven? Roll up to each dimension separately.
CREATE OR REPLACE VIEW v_variance_by_store AS
SELECT
    t5StoreNumber,
    siteName,
    COUNT(DISTINCT period || '|' || fleetCode) AS fleetMonthsTouched,
    SUM(variance)                              AS netVariance,
    SUM(abs(variance))                         AS absVariance
FROM v_variance_fleet_store_month
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;

CREATE OR REPLACE VIEW v_variance_by_fleet AS
SELECT
    fleetCode,
    fleetName,
    COUNT(DISTINCT period || '|' || t5StoreNumber) AS storeMonthsTouched,
    SUM(variance)                                  AS netVariance,
    SUM(abs(variance))                             AS absVariance
FROM v_variance_fleet_store_month
WHERE reconStatus = 'variance'
GROUP BY 1, 2
ORDER BY absVariance DESC;
