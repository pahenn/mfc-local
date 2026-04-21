-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: product / service-type breakdown
-- Supports the "what products drove variances" question. Joins line items
-- back to the fleet/store/period grain so variances at the rollup can be
-- traced to specific SKUs.
-- ─────────────────────────────────────────────────────────────────────────

-- Line items enriched with the parent fleet / store / period
CREATE OR REPLACE VIEW v_line_enriched AS
SELECT
    iib.invoiceItemBridgeID,
    iib.invoiceID,
    iib.serviceCatgCode,
    iib.itemDescription,
    iib.serviceActualQuantity,
    iib.serviceAmount,
    iib.serviceActualAmount,
    ie.period,
    ie.fleetCode,
    ie.fleetName,
    ie.t5StoreNumber,
    ie.siteName
FROM invoice_item_bridge iib
  INNER JOIN v_invoice_enriched ie ON ie.invoiceID = iib.invoiceID;

-- Per-SKU rollup across the whole window (sortable to find top movers)
CREATE OR REPLACE VIEW v_product_totals AS
SELECT
    serviceCatgCode,
    itemDescription,
    COUNT(*)                  AS lineCount,
    SUM(serviceActualQuantity) AS totalQuantity,
    SUM(serviceActualAmount)   AS totalRevenue
FROM v_line_enriched
GROUP BY 1, 2
ORDER BY totalRevenue DESC;

-- Per-store product mix — answers "is this a shop issue or a product issue?"
CREATE OR REPLACE VIEW v_store_product_mix AS
SELECT
    t5StoreNumber,
    siteName,
    serviceCatgCode,
    SUM(serviceActualAmount) AS revenue,
    COUNT(*)                 AS lines
FROM v_line_enriched
GROUP BY 1, 2, 3
ORDER BY t5StoreNumber, revenue DESC;

-- Bucketed into the common service types (matches the sales-dashboard Q5 buckets)
CREATE OR REPLACE VIEW v_service_type_rollup AS
SELECT
    period,
    fleetCode,
    t5StoreNumber,
    CASE
        WHEN lower(coalesce(itemDescription, '')) LIKE '%oil change%' THEN 'Oil change'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%tire%'
          OR lower(coalesce(itemDescription, '')) LIKE '%rotation%'   THEN 'Tire service'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%engine filter%'
          OR lower(coalesce(itemDescription, '')) LIKE '%oil filter%' THEN 'Engine filters'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%cabin%'      THEN 'Cabin air filters'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%wiper%'      THEN 'Wipers'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%brake%'      THEN 'Brake service'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%battery%'    THEN 'Battery'
        WHEN lower(coalesce(itemDescription, '')) LIKE '%labor%'      THEN 'Labor'
        ELSE 'Other'
    END AS serviceType,
    SUM(serviceActualAmount) AS revenue,
    COUNT(*)                 AS lines
FROM v_line_enriched
GROUP BY 1, 2, 3, 4
ORDER BY period DESC, fleetCode, t5StoreNumber, revenue DESC;
