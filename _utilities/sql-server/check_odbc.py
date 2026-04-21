#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pyodbc",
# ]
# ///
"""
Check ODBC configuration
"""

import pyodbc
import subprocess
import os

print("=" * 60)
print("ODBC Configuration Diagnostic")
print("=" * 60)

print("\n1. Available ODBC Drivers (via pyodbc):")
drivers = pyodbc.drivers()
if drivers:
    for driver in drivers:
        print(f"  - {driver}")
else:
    print("  (none found)")

print("\n2. odbcinst.ini location:")
result = subprocess.run(['odbcinst', '-j'], capture_output=True, text=True)
print(result.stdout)

print("\n3. Checking for FreeTDS driver files:")
freetds_paths = [
    '/opt/homebrew/lib/libtdsodbc.so',
    '/usr/local/lib/libtdsodbc.so',
    '/opt/homebrew/Cellar/freetds',
]

for path in freetds_paths:
    if os.path.exists(path):
        print(f"  ✓ Found: {path}")
    else:
        print(f"  ✗ Not found: {path}")

print("\n4. Registered drivers in odbcinst.ini:")
result = subprocess.run(['odbcinst', '-q', '-d'], capture_output=True, text=True)
if result.stdout.strip():
    print(result.stdout)
else:
    print("  (none registered)")

print("\n" + "=" * 60)
print("If FreeTDS is installed but not registered, run:")
print("  ./setup_freetds.sh")
print("=" * 60)
