-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: reconciliation view — Fleet × Store × Month
-- One row per (fleetCode, storeNumber, period).
--
-- Join path (matches the MFC legacy stored procs):
--   Invoice.SiteID     → Site.SiteID              (global store master)
--   Invoice.FleetID    → Fleet.FleetID
--   Invoice.CustomerID → Customer.CustomerID → CorporationTypes
--
-- Fee model:
--   totalMfcFee  = invoiceInvoiceFee
--   totalAiFee   = customer → brand cascade, flat + pct × invoiceTotalAmount.
--                  Simplified (no minimum-floor or AIFeeOverride lookup).
--
-- T5 store number:
--   Raw Site.Store_Number is 'T5C12345' or 'T5C12345828'. Parse out the
--   integer portion in the middle (strip 3-char prefix, plus 3-char '828'
--   suffix when present). Matches MFC_Reports_Automated_Take5_Invoice_* logic.
-- ─────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_invoice_enriched AS
SELECT
    i.invoiceID,
    i.invoiceNumber,
    i.invoiceDate,
    date_trunc('month', CAST(i.invoiceDate AS DATE)) AS period,

    -- Fleet grain
    f.fleetID,
    f.fleetCode,
    f.fleetAccountName  AS fleetName,

    -- Store grain
    s.siteID,
    CASE
      WHEN s.storeNumber LIKE '%828' AND length(s.storeNumber) > 6
        THEN TRY_CAST(substring(s.storeNumber, 4, length(s.storeNumber) - 6) AS INTEGER)
      WHEN length(s.storeNumber) > 3
        THEN TRY_CAST(substring(s.storeNumber, 4, length(s.storeNumber) - 3) AS INTEGER)
      ELSE NULL
    END                 AS storeNumber,
    s.siteName,
    s.region,
    s.district,
    s.division,

    -- Customer (service provider)
    c.customerID,
    c.customerCompanyName AS customerName,
    c.corpType,

    -- Raw money columns needed for the rollup
    i.invoiceTotalAmount,
    i.prepaidTotalAmount,
    (i.invoiceTotalAmount - COALESCE(i.prepaidTotalAmount, 0)) AS mfcBalance,
    i.invoiceTaxTotalAmount,
    i.invoiceTotalDiscounts,
    i.invoiceCCFees,

    -- MFC fee → single column
    COALESCE(i.invoiceInvoiceFee, 0) AS totalMfcFee,

    -- AI fee: customer → brand cascade, flat + pct of invoiceTotalAmount
    (COALESCE(c.aiInvoiceFlatFee, 0)
     + i.invoiceTotalAmount
       * COALESCE(c.aiInvoicePctFee, ct.aiFeePct, 0)
    ) AS totalAiFee,

    -- Flags
    i.voided
FROM invoices i
  LEFT JOIN fleets            f  ON f.fleetID           = i.fleetID
  LEFT JOIN sites             s  ON s.siteID            = i.siteID
  LEFT JOIN customers         c  ON c.customerID        = i.customerID
  LEFT JOIN corporation_types ct ON ct.corporationType  = c.corpType;


-- ─────────────────────────────────────────────────────────────────────────
-- Main reconciliation row — one per (fleet, store, month)
-- ─────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_fleet_store_month AS
SELECT
    period,
    fleetCode,
    fleetName,
    storeNumber,
    siteName,
    COUNT(DISTINCT invoiceID)  AS invoiceCount,
    SUM(invoiceTotalAmount)    AS totalInvoice,
    SUM(mfcBalance)            AS mfcTotalBalance,
    SUM(invoiceTaxTotalAmount) AS totalTax,
    SUM(invoiceTotalDiscounts) AS totalDiscount,
    SUM(invoiceCCFees)         AS totalCcFee,
    SUM(totalMfcFee)           AS totalMfcFee,
    SUM(totalAiFee)            AS totalAiFee,
    MIN(invoiceDate)           AS firstInvoiceDate,
    MAX(invoiceDate)           AS lastInvoiceDate
FROM v_invoice_enriched
GROUP BY 1, 2, 3, 4, 5
ORDER BY period DESC, fleetName, storeNumber;

SELECT * FROM v_fleet_store_month LIMIT 50;
