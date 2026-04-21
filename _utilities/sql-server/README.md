# SQL Server utilities — local

Copied (and trimmed) from `platform/_utilities/sql-server/`. Everything here reads credentials from `local/.env`.

## Files

| Tool | What it does |
|---|---|
| `check_odbc.py` | Lists installed ODBC drivers, verifies FreeTDS setup. Run this first if anything fails. |
| `setup_freetds.sh` | One-time FreeTDS config for macOS. Only needed if `check_odbc.py` can't find a driver. |
| `run_sql.py` | Runs a .sql file and prints results to stdout. For one-off queries / debugging. |
| `extract_to_csv.py` | Runs a SELECT .sql file and streams results to a CSV. Used by the extract pipelines. |

## Prereqs

```bash
brew install unixodbc freetds    # ODBC + SQL Server driver on macOS
```

`uv` handles the Python deps automatically (`#!/usr/bin/env -S uv run --script`).

## .env at `local/.env`

```
DB_SERVER=your-server.whatever.net
DB_DATABASE=your_database
DB_USER=your_user
DB_PASSWORD=your_password
DB_PORT=1433          # optional
TDS_VERSION=7.4       # optional, FreeTDS only
```

Never commit this file.

## Typical usage

```bash
# From local/
./_utilities/sql-server/check_odbc.py
./_utilities/sql-server/extract_to_csv.py driven-brands-analytics/queries/extract/05_invoices.sql driven-brands-analytics/source-data/invoices.csv

# Or let the wrapper do all six
./driven-brands-analytics/scripts/run_extracts.sh
```
