-- ─────────────────────────────────────────────────────────────────────────
-- Extract: Fleet (the fleet customer buying services)
-- Purpose: fleet code + fleet company name for the reconciliation grain
-- Scope:   Only fleets with at least one invoice against a T5C/MBL customer
--          in the rolling window (current month + 3 prior).
-- Output:  fleets.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    f.[FleetID]                     AS fleetID,
    f.[Fleet_Code]                  AS fleetCode,
    -- Match the shape Driven Brands uses in their KPI export:
    --   fleetAccountNumber = the numeric portion of Fleet_Code (same value as FleetID)
    --   fleetAccountName   = the fleet's company name
    f.[FleetID]                     AS fleetAccountNumber,
    f.[Fleet_CompanyName]           AS fleetAccountName,
    f.[Fleet_Credit]                AS fleetCredit,
    f.[Fleet_Credit_PreLive]        AS fleetCreditPreLive,
    f.[Fleet_CreatedOn]             AS fleetCreatedOn,
    f.[Fleet_StartDate]             AS fleetStartDate,
    f.[Fleet_StopDate]              AS fleetStopDate,
    f.[Fleet_AccountClosed]         AS fleetAccountClosed,
    f.[Fleet_NationalAccount]       AS fleetNationalAccount,
    f.[UniqueAccountIdentifier]     AS uniqueAccountIdentifier
FROM [Fleet] f
WHERE f.[FleetID] IN (
    SELECT DISTINCT i.[FleetID]
    FROM [Invoice] i
      INNER JOIN [Customer] c ON c.[CustomerID] = i.[CustomerID]
    WHERE c.[CorpType] IN ('T5C', 'MBL')
      AND i.[Invoice_Date] >= DATEADD(month, -3, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
      AND i.[voided] = 0
);
