#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pyodbc", "python-dotenv"]
# ///
"""Sample dbo.BrandNames + check whether existing CorporationTypes.BrandId
values join to BrandNames.BrandId (nvarchar) or BrandNames.BrandNameId (int)."""
from __future__ import annotations

import os
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def conn() -> pyodbc.Connection:
    drv = next((d for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "FreeTDS"] if d in pyodbc.drivers()))
    if drv == "FreeTDS":
        cs = (
            f"DRIVER={{{drv}}};SERVER={os.getenv('DB_SERVER')};PORT={os.getenv('DB_PORT','1433')};"
            f"DATABASE={os.getenv('DB_DATABASE')};UID={os.getenv('DB_USER')};PWD={os.getenv('DB_PASSWORD')};"
            f"TDS_Version={os.getenv('TDS_VERSION','7.4')};"
        )
    else:
        cs = (
            f"DRIVER={{{drv}}};SERVER={os.getenv('DB_SERVER')};DATABASE={os.getenv('DB_DATABASE')};"
            f"UID={os.getenv('DB_USER')};PWD={os.getenv('DB_PASSWORD')};TrustServerCertificate=yes;"
        )
    return pyodbc.connect(cs)


def show(cur, title: str) -> None:
    print("\n" + "=" * 80 + f"\n{title}\n" + "=" * 80)
    if cur.description is None:
        print("(no result set)"); return
    cols = [d[0] for d in cur.description]
    rows = [[("NULL" if v is None else str(v)) for v in r] for r in cur.fetchall()]
    widths = [len(c) for c in cols]
    for r in rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(v))
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*cols))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))
    print(f"({len(rows)} row(s))")


def main() -> None:
    with conn() as c:
        cur = c.cursor()

        # Total + sample
        cur.execute("SELECT COUNT(*) FROM dbo.BrandNames")
        print(f"BrandNames row count: {cur.fetchone()[0]}")

        cur.execute("SELECT TOP 25 BrandNameId, BrandId, BrandName, CreatedOn FROM dbo.BrandNames ORDER BY BrandNameId")
        show(cur, "First 25 BrandNames")

        # Look for the BrandId integers used by the OEM rows in CorporationTypes
        sample_oem_ids = ['32015', '32114', '39375', '39368', '34121', '32990', '32002']
        in_clause = ",".join(f"'{i}'" for i in sample_oem_ids)
        cur.execute(f"""
            SELECT BrandNameId, BrandId, BrandName
            FROM   dbo.BrandNames
            WHERE  BrandId IN ({in_clause})
            ORDER  BY TRY_CAST(BrandId AS INT)
        """)
        show(cur, f"BrandNames where BrandId matches OEM CorporationTypes.BrandId values ({in_clause})")

        # Same set, but matching BrandNameId (the int PK) instead
        int_in = ",".join(sample_oem_ids)
        cur.execute(f"""
            SELECT BrandNameId, BrandId, BrandName
            FROM   dbo.BrandNames
            WHERE  BrandNameId IN ({int_in})
            ORDER  BY BrandNameId
        """)
        show(cur, f"BrandNames where BrandNameId matches the same OEM int values")

        # Distribution: how many BrandNames.BrandId values are numeric strings?
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN TRY_CAST(BrandId AS INT) IS NOT NULL THEN 1 ELSE 0 END) AS numeric_brandids,
                MIN(TRY_CAST(BrandId AS INT)) AS min_int,
                MAX(TRY_CAST(BrandId AS INT)) AS max_int
            FROM dbo.BrandNames
        """)
        show(cur, "BrandId numeric distribution")


if __name__ == "__main__":
    main()
