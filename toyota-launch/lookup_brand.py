#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pyodbc",
#   "python-dotenv",
# ]
# ///
"""Look up Toyota in dbo.BrandNames so we can plug a real BrandId into the insert."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

SERVER   = os.getenv("DB_SERVER")
DATABASE = os.getenv("DB_DATABASE")
USERNAME = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASSWORD")
PORT     = os.getenv("DB_PORT", "1433")
TDS_VER  = os.getenv("TDS_VERSION", "7.4")


def pick_driver() -> str:
    for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "FreeTDS"]:
        if d in pyodbc.drivers():
            return d
    print("No SQL Server ODBC driver found", file=sys.stderr)
    sys.exit(1)


def conn_string() -> str:
    drv = pick_driver()
    if drv == "FreeTDS":
        return (
            f"DRIVER={{{drv}}};SERVER={SERVER};PORT={PORT};DATABASE={DATABASE};"
            f"UID={USERNAME};PWD={PASSWORD};TDS_Version={TDS_VER};"
        )
    return f"DRIVER={{{drv}}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;"


def print_rows(cursor) -> None:
    if cursor.description is None:
        print("(no result set)")
        return
    cols = [d[0] for d in cursor.description]
    rows = [[("NULL" if v is None else str(v)) for v in r] for r in cursor.fetchall()]
    widths = [len(c) for c in cols]
    for r in rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(v))
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*cols))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))
    print(f"\n({len(rows)} row(s))\n")


def main() -> None:
    with pyodbc.connect(conn_string()) as conn:
        cur = conn.cursor()

        # 1. Does dbo.BrandNames exist? Show its columns.
        print("=" * 80)
        print("dbo.BrandNames — column metadata")
        print("=" * 80)
        cur.execute(
            """
            SELECT  c.COLUMN_NAME, c.ORDINAL_POSITION, c.DATA_TYPE,
                    c.CHARACTER_MAXIMUM_LENGTH, c.IS_NULLABLE
            FROM    INFORMATION_SCHEMA.COLUMNS c
            WHERE   c.TABLE_SCHEMA = 'dbo' AND c.TABLE_NAME = 'BrandNames'
            ORDER BY c.ORDINAL_POSITION
            """
        )
        cols_rows = cur.fetchall()
        if not cols_rows:
            print("dbo.BrandNames not found — looking for tables with 'brand' in the name…")
            cur.execute(
                """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM   INFORMATION_SCHEMA.TABLES
                WHERE  TABLE_NAME LIKE '%[Bb]rand%'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
            )
            print_rows(cur)
            return

        col_names = [r[0] for r in cols_rows]
        print(" | ".join(["COLUMN_NAME", "ORD", "TYPE", "LEN", "NULLABLE"]))
        for r in cols_rows:
            print(" | ".join("NULL" if v is None else str(v) for v in r))
        print(f"\n({len(cols_rows)} columns)\n")

        # 2. Find a likely "name" column and search for Toyota.
        name_candidates = [c for c in col_names if c.lower() in ("brandname", "name", "branddescription", "description")]
        print("=" * 80)
        print(f"dbo.BrandNames — rows matching 'toyota' (search columns: {name_candidates})")
        print("=" * 80)
        if name_candidates:
            where = " OR ".join(f"[{c}] LIKE '%toyota%'" for c in name_candidates)
            cur.execute(f"SELECT TOP 25 * FROM dbo.BrandNames WHERE {where}")
            print_rows(cur)
        else:
            print("(no obvious name column; printing first 25 rows so you can eyeball)\n")
            cur.execute("SELECT TOP 25 * FROM dbo.BrandNames")
            print_rows(cur)


if __name__ == "__main__":
    main()
