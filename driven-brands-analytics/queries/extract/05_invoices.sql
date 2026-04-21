-- ─────────────────────────────────────────────────────────────────────────
-- Extract: Invoice (header)
-- Purpose: main fact table. Raw dump filtered to T5C/MBL + date window.
-- Scope:   CorpType IN ('T5C','MBL'), Invoice_Date in current month + 3 prior,
--          voided = 0.
-- Output:  invoices.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    i.[InvoiceID]                          AS invoiceID,
    i.[Invoice_Number]                     AS invoiceNumber,
    i.[Invoice_LinkGUID]                   AS invoiceLinkGUID,
    i.[CustomerID]                         AS customerID,
    i.[FleetID]                            AS fleetID,
    i.[SiteID]                             AS siteID,
    i.[VehicleID]                          AS vehicleID,
    i.[LicenseID]                          AS licenseID,
    i.[DriverID]                           AS driverID,

    -- Dates
    i.[Invoice_Date]                       AS invoiceDate,
    i.[Invoice_StatementDate]              AS invoiceStatementDate,
    i.[Invoice_StatementDueDate]           AS invoiceStatementDueDate,
    i.[Invoice_Paidon]                     AS invoicePaidon,
    i.[Invoice_PaidOutOn]                  AS invoicePaidOutOn,
    i.[Invoice_BilledOutOn]                AS invoiceBilledOutOn,
    i.[Invoice_FinanceChargeDate]          AS invoiceFinanceChargeDate,
    i.[Invoice_ExtendedDueDate]            AS invoiceExtendedDueDate,
    i.[createdon]                          AS createdon,
    i.[ImportDate]                         AS importDate,

    -- Money: totals, payments, adjustments, discounts
    i.[Invoice_Total_Amount]               AS invoiceTotalAmount,
    i.[Invoice_Tax_Total_Amount]           AS invoiceTaxTotalAmount,
    i.[Prepaid_Total_Amount]               AS prepaidTotalAmount,
    i.[Invoice_TotalPaymentsReceived]      AS invoiceTotalPaymentsReceived,
    i.[Invoice_TotalPaymentsSent]          AS invoiceTotalPaymentsSent,
    i.[Invoice_TotalAdjustments]           AS invoiceTotalAdjustments,
    i.[Invoice_TotalDiscounts]             AS invoiceTotalDiscounts,
    i.[Invoice_ComputedDiscount]           AS invoiceComputedDiscount,
    i.[Discount_Total_Amount]              AS discountTotalAmount,
    i.[Fleet_Discount_Base_Amount]         AS fleetDiscountBaseAmount,
    i.[Fleet_Computed_Discount_Amount]     AS fleetComputedDiscountAmount,
    i.[Fleet_Debit_Amount]                 AS fleetDebitAmount,

    -- Money: fees (persisted-at-write values)
    i.[Invoice_CCFees]                     AS invoiceCCFees,
    i.[Invoice_FinanceCharge]              AS invoiceFinanceCharge,
    i.[Invoice_MiscFees]                   AS invoiceMiscFees,
    i.[Invoice_FactoringFees]              AS invoiceFactoringFees,
    i.[Invoice_InvoiceFee]                 AS invoiceInvoiceFee,
    i.[Invoice_InvoiceFee_Store]           AS invoiceInvoiceFeeStore,
    i.[Invoice_InvoiceFee_CoOp]            AS invoiceInvoiceFeeCoOp,
    i.[Invoice_Temp_FinanceFee]            AS invoiceTempFinanceFee,
    i.[Invoice_BillingFees_AutoIntegrate]  AS invoiceBillingFeesAutoIntegrate,
    i.[AIFee]                              AS aiFee,

    -- Store number override on invoice row (set at import time)
    i.[Invoice_Import_Store_Number]        AS invoiceImportStoreNumber,

    -- Factoring
    i.[Invoice_Factored]                   AS invoiceFactored,
    i.[Invoice_Factored_CustomerID]        AS invoiceFactoredCustomerID,
    i.[Invoice_Factored_PurchasedOn]       AS invoiceFactoredPurchasedOn,

    -- Status
    i.[Pending]                            AS pending,
    i.[voided]                             AS voided
FROM [Invoice] i
  INNER JOIN [Customer] c ON c.[CustomerID] = i.[CustomerID]
WHERE c.[CorpType] IN ('T5C', 'MBL')
  AND i.[Invoice_Date] >= DATEADD(month, -3, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
  AND i.[voided] = 0;
