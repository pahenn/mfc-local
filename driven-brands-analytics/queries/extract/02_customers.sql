-- ─────────────────────────────────────────────────────────────────────────
-- Extract: Customer (service-provider-level in MFC parlance)
-- Purpose: customer-level fee overrides (cascade layer between brand & site)
-- Scope:   Customers whose CorpType is Take 5 (T5C) or MBL.
-- Output:  customers.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    c.[CustomerID]              AS customerID,
    c.[Customer_CompanyName]    AS customerCompanyName,
    c.[CorpType]                AS corpType,
    c.[Customer_CreatedOn]      AS customerCreatedOn,
    c.[Customer_InvoiceFee]     AS customerInvoiceFee,
    c.[invoicePctFee]           AS invoicePctFee,
    c.[invoiceMinimumFee]       AS invoiceMinimumFee,
    c.[invoiceFlatFee]          AS invoiceFlatFee,
    c.[aiFee]                   AS aiFee,
    c.[aiInvoicePctFee]         AS aiInvoicePctFee,
    c.[aiInvoiceFlatFee]        AS aiInvoiceFlatFee,
    c.[aiInvoiceMinimumFee]     AS aiInvoiceMinimumFee,
    c.[aiCutPctFee]             AS aiCutPctFee,
    c.[aiCutFlatFee]            AS aiCutFlatFee,
    c.[factoredPct]             AS factoredPct,
    c.[factoredMultiplier]      AS factoredMultiplier,
    c.[factoredDiscounts]       AS factoredDiscounts,
    c.[factoredTypeId]          AS factoredTypeId
FROM [Customer] c
WHERE c.[CorpType] IN ('T5C', 'MBL');
