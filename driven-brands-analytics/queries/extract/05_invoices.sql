-- ─────────────────────────────────────────────────────────────────────────
-- Extract: Invoice (header)
-- Purpose: main fact table. Raw dump filtered to T5C/MBL + date window.
-- Scope:   CorpType IN ('T5C','MBL'), Invoice_Date in current month + 3 prior.
--          Voided invoices are INCLUDED — filter downstream in the dashboard.
-- Output:  invoices.csv
--
-- Columns are pared down to exactly what the dashboard's v_invoice_enriched
-- view consumes, plus invoiceImportStoreNumber (kept as a candidate Driven
-- Brands join key — see queries/extract/README.md) and voided (kept so the
-- dashboard can toggle voided invoices in/out).
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    i.[InvoiceID]                          AS invoiceID,
    i.[Invoice_Number]                     AS invoiceNumber,
    i.[CustomerID]                         AS customerID,
    i.[FleetID]                            AS fleetID,
    i.[SiteID]                             AS siteID,

    -- Date (only invoiceDate is used by the rollup)
    i.[Invoice_Date]                       AS invoiceDate,

    -- Money: totals, prepaid, discounts, CC fee, MFC fee
    i.[Invoice_Total_Amount]               AS invoiceTotalAmount,
    i.[Invoice_Tax_Total_Amount]           AS invoiceTaxTotalAmount,
    i.[Prepaid_Total_Amount]               AS prepaidTotalAmount,
    i.[Invoice_TotalDiscounts]             AS invoiceTotalDiscounts,
    i.[Invoice_CCFees]                     AS invoiceCCFees,
    i.[Invoice_InvoiceFee]                 AS invoiceInvoiceFee,

    -- Store number override on invoice row (kept for reconciliation — TBD)
    i.[Invoice_Import_Store_Number]        AS invoiceImportStoreNumber,

    -- AutoIntegrate / "AI invoice" signals. The dashboard derives
    -- isAiInvoice = (invoiceBilledOutOnAutoIntegrate IS NOT NULL)
    --            OR (invoiceBillingFeesAutoIntegrate > 0)
    i.[Invoice_BilledOutOn_AutoIntegrate]  AS invoiceBilledOutOnAutoIntegrate,
    i.[Invoice_BillingFees_AutoIntegrate]  AS invoiceBillingFeesAutoIntegrate,

    -- Flags
    i.[voided]                             AS voided
FROM [Invoice] i
  INNER JOIN [Customer] c ON c.[CustomerID] = i.[CustomerID]
WHERE c.[CorpType] IN ('T5C', 'MBL')
  AND i.[Invoice_Date] >= DATEADD(month, -3, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1));
