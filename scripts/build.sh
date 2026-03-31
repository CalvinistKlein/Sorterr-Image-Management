#!/bin/bash
# ============================================================
#  Sorterr - Linux / macOS Build Script
# ============================================================
set -e
cd "$(dirname "$0")/.."

# --- Check venv ---
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found."
    echo "Run: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "[1/3] Installing / verifying build tools..."
./venv/bin/pip install pyinstaller -q

echo "[2/3] Cleaning previous build..."
rm -rf build/ dist/ *.spec

echo "[3/3] Building Sorterr binary..."

# Try with icon first; fall back silently if it doesn't exist
ICON_OPT=""
[ -f "web/favicon.ico" ] && ICON_OPT="--icon web/favicon.ico"

./venv/bin/pyinstaller \
    --onefile \
    --add-data "web:web" \
    --collect-all rawpy \
    --collect-all exifread \
    --name "Sorterr" \
    $ICON_OPT \
    main.py

echo ""
echo "============================================================"
echo "  Build complete!"
echo "  Binary: $(pwd)/dist/Sorterr"
echo "============================================================"
