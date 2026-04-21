#!/bin/bash
# Setup FreeTDS ODBC driver for use with pyodbc

set -e

echo "========================================"
echo "FreeTDS ODBC Setup"
echo "========================================"

# Find FreeTDS library
FREETDS_LIB=""

if [ -f "/opt/homebrew/lib/libtdsodbc.so" ]; then
    FREETDS_LIB="/opt/homebrew/lib/libtdsodbc.so"
elif [ -f "/usr/local/lib/libtdsodbc.so" ]; then
    FREETDS_LIB="/usr/local/lib/libtdsodbc.so"
else
    echo "Error: FreeTDS library not found"
    echo "Please install it with: brew install freetds"
    exit 1
fi

echo "Found FreeTDS library: $FREETDS_LIB"

# Get odbcinst.ini location
ODBCINST_INI=$(odbcinst -j | grep "DRIVERS" | awk '{print $2}')

echo "odbcinst.ini location: $ODBCINST_INI"

# Check if FreeTDS is already registered
if odbcinst -q -d | grep -q "FreeTDS"; then
    echo ""
    echo "✓ FreeTDS is already registered"
    echo ""
    odbcinst -q -d -n "FreeTDS"
else
    echo ""
    echo "Registering FreeTDS driver..."

    # Create temporary config file
    cat > /tmp/freetds_driver.ini << EOF
[FreeTDS]
Description = FreeTDS Driver
Driver = $FREETDS_LIB
Setup = $FREETDS_LIB
UsageCount = 1
EOF

    # Register driver
    sudo odbcinst -i -d -f /tmp/freetds_driver.ini

    echo "✓ FreeTDS driver registered"
    rm /tmp/freetds_driver.ini
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "You can now run: ./export_procedures.py"
echo "========================================"
