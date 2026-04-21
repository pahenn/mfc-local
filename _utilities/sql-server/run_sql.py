#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pyodbc",
#   "python-dotenv",
# ]
# ///
"""
Execute SQL files using pyodbc (sqlcmd alternative)
Usage: ./run_sql.py <sql_file>
Example: ./run_sql.py verify_fee_type_codes.sql

Reads database configuration from .env file in project root.
"""

import pyodbc
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from local repo root (2 levels up: sql-server/ → _utilities/ → local/)
project_root = Path(__file__).resolve().parents[2]
env_file = project_root / '.env'

if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"Warning: .env file not found at {env_file}")
    sys.exit(1)

# Read configuration from environment variables
SERVER = os.getenv('DB_SERVER') or os.getenv('DATABASE_HOST', 'localhost')
DATABASE = os.getenv('DB_DATABASE') or os.getenv('DB_NAME') or os.getenv('DATABASE_NAME')
USERNAME = os.getenv('DB_USER') or os.getenv('DATABASE_USER', '')
PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('DATABASE_PASSWORD', '')
USE_WINDOWS_AUTH = os.getenv('DB_USE_WINDOWS_AUTH', 'false').lower() == 'true'

# Detect available SQL Server ODBC driver
def get_odbc_driver():
    """Find available SQL Server ODBC driver"""
    drivers = pyodbc.drivers()

    preferred_drivers = [
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server',
        'ODBC Driver 13 for SQL Server',
        'FreeTDS',
    ]

    for driver in preferred_drivers:
        if driver in drivers:
            return driver

    raise ValueError("No SQL Server ODBC driver found")

ODBC_DRIVER = get_odbc_driver()

# Build connection string
if USE_WINDOWS_AUTH:
    CONNECTION_STRING = f'DRIVER={{{ODBC_DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;'
else:
    if not USERNAME or not PASSWORD:
        raise ValueError("SQL Authentication requires DB_USER and DB_PASSWORD in .env file")

    if ODBC_DRIVER == 'FreeTDS':
        PORT = os.getenv('DB_PORT', '1433')
        TDS_VERSION = os.getenv('TDS_VERSION', '7.4')
        CONNECTION_STRING = (
            f'DRIVER={{{ODBC_DRIVER}}};'
            f'SERVER={SERVER};'
            f'PORT={PORT};'
            f'DATABASE={DATABASE};'
            f'UID={USERNAME};'
            f'PWD={PASSWORD};'
            f'TDS_Version={TDS_VERSION};'
        )
    else:
        CONNECTION_STRING = f'DRIVER={{{ODBC_DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};'

def execute_sql_file(filepath):
    """Execute a SQL file and print results"""
    # Read SQL file
    sql_path = Path(filepath)
    if not sql_path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    sql_content = sql_path.read_text(encoding='utf-8')

    print(f"Executing: {sql_path.name}")
    print(f"Database: {SERVER} / {DATABASE}")
    print("=" * 60)
    print()

    # Connect to database
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        conn.autocommit = True  # Similar to sqlcmd behavior
        cursor = conn.cursor()

        # Split SQL into batches (GO statements)
        batches = sql_content.split('\nGO\n')

        for i, batch in enumerate(batches):
            batch = batch.strip()
            if not batch or batch.startswith('--'):
                continue

            try:
                # Execute batch
                cursor.execute(batch)

                # Print PRINT statements (messages)
                while cursor.nextset():
                    pass

                # Fetch and display results if any
                if cursor.description:
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]

                    # Print header
                    print(" | ".join(columns))
                    print("-" * 60)

                    # Print rows
                    rows = cursor.fetchall()
                    for row in rows:
                        print(" | ".join(str(val) if val is not None else 'NULL' for val in row))

                    print()
                    print(f"({len(rows)} row(s) affected)")
                    print()

            except pyodbc.Error as e:
                print(f"Error in batch {i + 1}:")
                print(str(e))
                print()

        # Print server messages (PRINT statements)
        for message in cursor.messages:
            print(message[1])

        cursor.close()
        conn.close()

        print()
        print("=" * 60)
        print("Execution complete")

    except pyodbc.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: ./run_sql.py <sql_file>")
        print("Example: ./run_sql.py verify_fee_type_codes.sql")
        sys.exit(1)

    sql_file = sys.argv[1]
    execute_sql_file(sql_file)
