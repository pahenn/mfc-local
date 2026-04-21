#!/usr/bin/env bash
# Run all six extract queries against the MFC legacy MSSQL and write the
# results to ../source-data/ with the filenames the DuckDB loader expects.
#
# Requires: local/.env with DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD.
#           ODBC driver installed (`../_utilities/sql-server/check_odbc.py`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXTRACTOR="$PROJECT_DIR/../_utilities/sql-server/extract_to_csv.py"
EXTRACT_SQL="$PROJECT_DIR/queries/extract"
OUT_DIR="$PROJECT_DIR/source-data"

mkdir -p "$OUT_DIR"

# (source-sql-basename, output-csv-basename)
pairs=(
  "01_corporation_types:corporation_types"
  "02_customers:customers"
  "03_sites:sites"
  "04_fleets:fleets"
  "05_invoices:invoices"
  "06_invoice_item_bridge:invoice_item_bridge"
)

for pair in "${pairs[@]}"; do
  src="${pair%%:*}"
  dst="${pair##*:}"
  "$EXTRACTOR" "$EXTRACT_SQL/${src}.sql" "$OUT_DIR/${dst}.csv"
done

echo
echo "All extracts complete. CSVs in: $OUT_DIR"
