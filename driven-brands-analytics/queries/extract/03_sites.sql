-- ─────────────────────────────────────────────────────────────────────────
-- Extract: Site (THE table Invoice.SiteID actually joins to)
-- Purpose: physical store master — Store_Number, Site_Name, address.
-- Scope:   Sites whose Store_Number matches a CorporationPrefix for T5C/MBL.
--          Avoids the Invoice scan entirely — orders-of-magnitude faster.
-- Output:  sites.csv
-- ─────────────────────────────────────────────────────────────────────────
SELECT
    s.[SiteID]              AS siteID,
    s.[Store_Number]        AS storeNumber,
    s.[Site_Name]           AS siteName,
    s.[Site_Street_Address] AS siteStreetAddress,
    s.[Site_City_Name]      AS siteCityName,
    s.[Site_State_Code]     AS siteStateCode,
    s.[Site_Zip_Code]       AS siteZipCode,
    s.[Site_Phone_Number]   AS sitePhoneNumber,
    s.[district]            AS district,
    s.[division]            AS division,
    s.[region]              AS region,
    s.[type]                AS type
FROM [Site] s
WHERE s.[Store_Number] LIKE 'T5C%'
   OR s.[Store_Number] LIKE 'MBL%';
