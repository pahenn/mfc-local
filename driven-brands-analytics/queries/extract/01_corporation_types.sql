-- ─────────────────────────────────────────────────────────────────────────
-- Extract: CorporationTypes
-- Purpose: brand-level fee defaults + store-number formatting rules
-- Scope:   All rows. This is a small reference table; dumping everything
--          removes ambiguity about whether to match on CorporationType vs
--          CorporationPrefix, and lets DuckDB-side joins be explicit.
-- Output:  corporation_types.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    [CorporationTypeID]              AS corporationTypeID,
    [CorporationName]                AS corporationName,
    [CorporationType]                AS corporationType,
    [CorporationPrefix]              AS corporationPrefix,
    [StoreNumberLength]              AS storeNumberLength,
    [storeNumberPaddingCharacter]    AS storeNumberPaddingCharacter,
    [InvoicePercentFee]              AS invoicePercentFee,
    [InvoiceFlatFee]                 AS invoiceFlatFee,
    [AIFee]                          AS aiFee,
    [AIFeePct]                       AS aiFeePct,
    [AIMinimumFee]                   AS aiMinimumFee,
    [AICutFlatFee]                   AS aiCutFlatFee,
    [AICutPercentFee]                AS aiCutPercentFee
FROM [CorporationTypes];
