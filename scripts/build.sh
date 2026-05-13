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

# Determine icon based on OS
ICON_FLAG=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    [ -f "assets/icon.icns" ] && ICON_FLAG="--icon assets/icon.icns"
else
    [ -f "assets/icon.ico" ] && ICON_FLAG="--icon assets/icon.ico"
fi

./venv/bin/pyinstaller \
    --onefile \
    --add-data "web:web" \
    --collect-all rawpy \
    --collect-all exifread \
    --name "Sorterr" \
    $ICON_FLAG \
    main.py

echo ""
echo "============================================================"
echo "  Build complete!"
echo "  Binary: $(pwd)/dist/Sorterr"
echo "============================================================"
