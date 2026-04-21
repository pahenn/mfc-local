#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pyodbc",
#   "python-dotenv",
# ]
# ///
"""
Run a SELECT .sql file against SQL Server and stream the result rows to a CSV.

Usage:
    ./extract_to_csv.py <input.sql> <output.csv>

Reads DB credentials from ../.env (local/ repo root). The SQL file must be a
single SELECT statement (no GO batches, no side effects). Rows stream directly
to disk so large extracts don't have to fit in memory.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

# ── Credentials from .env at local repo root ──────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_file = PROJECT_ROOT / ".env"
if not env_file.exists():
    print(f"Error: .env not found at {env_file}", file=sys.stderr)
    sys.exit(1)
load_dotenv(env_file)

SERVER   = os.getenv("DB_SERVER")   or os.getenv("DATABASE_HOST")
DATABASE = os.getenv("DB_DATABASE") or os.getenv("DB_NAME") or os.getenv("DATABASE_NAME")
USERNAME = os.getenv("DB_USER")     or os.getenv("DATABASE_USER", "")
PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("DATABASE_PASSWORD", "")
WINDOWS_AUTH = os.getenv("DB_USE_WINDOWS_AUTH", "false").lower() == "true"

# ── ODBC driver discovery ─────────────────────────────────────────────────
def pick_driver() -> str:
    installed = pyodbc.drivers()
    for candidate in [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "FreeTDS",
    ]:
        if candidate in installed:
            return candidate
    raise RuntimeError(f"No SQL Server ODBC driver found. Installed: {installed}")

DRIVER = pick_driver()

if WINDOWS_AUTH:
    CONN_STR = f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;"
elif DRIVER == "FreeTDS":
    PORT = os.getenv("DB_PORT", "1433")
    TDS = os.getenv("TDS_VERSION", "7.4")
    CONN_STR = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};PORT={PORT};DATABASE={DATABASE};"
        f"UID={USERNAME};PWD={PASSWORD};TDS_Version={TDS};"
    )
else:
    CONN_STR = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        f"UID={USERNAME};PWD={PASSWORD};Encrypt=yes;TrustServerCertificate=yes;"
    )


def extract(sql_path: Path, csv_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"→ {sql_path.name}  ({DRIVER} @ {SERVER}/{DATABASE})")
    conn = pyodbc.connect(CONN_STR)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(columns)
            rows_written = 0
            # fetchmany loop keeps memory bounded
            while True:
                chunk = cursor.fetchmany(5000)
                if not chunk:
                    break
                w.writerows(chunk)
                rows_written += len(chunk)
                print(f"    … {rows_written:,} rows", end="\r", flush=True)
        print(f"    ✓ {rows_written:,} rows → {csv_path}")
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: ./extract_to_csv.py <input.sql> <output.csv>", file=sys.stderr)
        sys.exit(2)
    extract(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
