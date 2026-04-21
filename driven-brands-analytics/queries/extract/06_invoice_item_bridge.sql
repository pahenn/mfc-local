-- ─────────────────────────────────────────────────────────────────────────
-- Extract: InvoiceItemBridge (line items)
-- Purpose: product / service breakdown for variance drilldown
-- Scope:   Lines for invoices in 05_invoices.sql (same date + corpType window).
-- Output:  invoice_item_bridge.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    iib.[InvoiceItemBridgeID]      AS invoiceItemBridgeID,
    iib.[InvoiceID]                AS invoiceID,
    iib.[Service_Catg_Code]        AS serviceCatgCode,
    iib.[Item_Description]         AS itemDescription,
    iib.[Item_Detail]              AS itemDetail,
    iib.[Item_Price]               AS itemPrice,
    iib.[Service_Actual_Quantity]  AS serviceActualQuantity,
    iib.[Service_Amount]           AS serviceAmount,
    iib.[Service_Actual_Amount]    AS serviceActualAmount,
    iib.[Sales_Unit_Code]          AS salesUnitCode,
    iib.[Service_Validation_Code]  AS serviceValidationCode,
    iib.[Service_Location]         AS serviceLocation,
    iib.[LaborUnits]               AS laborUnits,
    iib.[Operation]                AS operation,
    iib.[Type]                     AS type,
    iib.[Item_CreatedOn]           AS itemCreatedOn
FROM [InvoiceItemBridge] iib
  INNER JOIN [Invoice]  i ON i.[InvoiceID]  = iib.[InvoiceID]
  INNER JOIN [Customer] c ON c.[CustomerID] = i.[CustomerID]
WHERE c.[CorpType] IN ('T5C', 'MBL')
  AND i.[Invoice_Date] >= DATEADD(month, -3, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND i.[voided] = 0;
