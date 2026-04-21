-- ─────────────────────────────────────────────────────────────────────────
-- DuckDB: load CSVs into tables
-- Run this first. Point the CSV paths at your source-data/ folder.
-- ─────────────────────────────────────────────────────────────────────────

-- If you're running from the repo root:
-- cd local/driven-brands-analytics && duckdb db.duckdb < queries/duckdb/00_load.sql

DROP TABLE IF EXISTS corporation_types;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS sites;
DROP TABLE IF EXISTS fleets;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS invoice_item_bridge;

CREATE TABLE corporation_types AS
SELECT * FROM read_csv_auto('source-data/corporation_types.csv', sample_size=-1);

CREATE TABLE customers AS
SELECT * FROM read_csv_auto('source-data/customers.csv', sample_size=-1);

CREATE TABLE sites AS
SELECT * FROM read_csv_auto('source-data/sites.csv', sample_size=-1);

CREATE TABLE fleets AS
SELECT * FROM read_csv_auto('source-data/fleets.csv', sample_size=-1);

CREATE TABLE invoices AS
SELECT * FROM read_csv_auto('source-data/invoices.csv', sample_size=-1);

CREATE TABLE invoice_item_bridge AS
SELECT * FROM read_csv_auto('source-data/invoice_item_bridge.csv', sample_size=-1);

-- Sanity-check row counts
SELECT 'corporation_types'   AS table_name, COUNT(*) AS rows FROM corporation_types
UNION ALL SELECT 'customers',           COUNT(*) FROM customers
UNION ALL SELECT 'sites',               COUNT(*) FROM sites
UNION ALL SELECT 'fleets',              COUNT(*) FROM fleets
UNION ALL SELECT 'invoices',            COUNT(*) FROM invoices
UNION ALL SELECT 'invoice_item_bridge', COUNT(*) FROM invoice_item_bridge
ORDER BY table_name;
