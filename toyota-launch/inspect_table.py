#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pyodbc",
#   "python-dotenv",
# ]
# ///
"""
Inspect dbo.CorporationTypes — column metadata + existing rows — so we can
craft a correct INSERT for the new Toyota corporation type.
"""
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
    cols = [d[0] for d in cursor.description]
    widths = [len(c) for c in cols]
    rows = [[("NULL" if v is None else str(v)) for v in r] for r in cursor.fetchall()]
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

        print("=" * 80)
        print("dbo.CorporationTypes — column metadata")
        print("=" * 80)
        cur.execute(
            """
            SELECT  c.COLUMN_NAME,
                    c.ORDINAL_POSITION,
                    c.DATA_TYPE,
                    c.CHARACTER_MAXIMUM_LENGTH,
                    c.IS_NULLABLE,
                    c.COLUMN_DEFAULT,
                    COLUMNPROPERTY(OBJECT_ID('dbo.CorporationTypes'), c.COLUMN_NAME, 'IsIdentity') AS IsIdentity
            FROM    INFORMATION_SCHEMA.COLUMNS c
            WHERE   c.TABLE_SCHEMA = 'dbo'
              AND   c.TABLE_NAME   = 'CorporationTypes'
            ORDER BY c.ORDINAL_POSITION
            """
        )
        print_rows(cur)

        print("=" * 80)
        print("dbo.CorporationTypes — primary key / unique constraints")
        print("=" * 80)
        cur.execute(
            """
            SELECT  kc.name        AS constraint_name,
                    kc.type_desc   AS constraint_type,
                    c.name         AS column_name,
                    ic.key_ordinal AS ordinal
            FROM    sys.key_constraints kc
            JOIN    sys.index_columns   ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
            JOIN    sys.columns         c  ON c.object_id  = ic.object_id        AND c.column_id  = ic.column_id
            WHERE   kc.parent_object_id = OBJECT_ID('dbo.CorporationTypes')
            ORDER BY kc.name, ic.key_ordinal
            """
        )
        print_rows(cur)

        print("=" * 80)
        print("dbo.CorporationTypes — existing rows")
        print("=" * 80)
        cur.execute("SELECT * FROM dbo.CorporationTypes ORDER BY CorporationName")
        print_rows(cur)


if __name__ == "__main__":
    main()
