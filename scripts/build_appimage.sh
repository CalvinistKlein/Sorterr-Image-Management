#!/bin/bash
set -e

# Configuration
APP_NAME="Sorterr"
APP_DIR="Sorterr.AppDir"
EXECUTABLE="../dist/Sorterr"
ICON="../assets/sorterr.png"
DESKTOP="../packaging/linux/sorterr.desktop"

echo "=== Building AppImage for $APP_NAME ==="

# 1. Prepare AppDir
echo "[1/4] Preparing AppDir..."
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/512x512/apps"

cp "$EXECUTABLE" "$APP_DIR/usr/bin/Sorterr"
cp "$ICON" "$APP_DIR/usr/share/icons/hicolor/512x512/apps/sorterr.png"
cp "$ICON" "$APP_DIR/sorterr.png"
cp "$DESKTOP" "$APP_DIR/sorterr.desktop"

# Create AppRun
cat <<EOF > "$APP_DIR/AppRun"
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
export PATH="\$HERE/usr/bin:\$PATH"
exec Sorterr "\$@"
EOF
chmod +x "$APP_DIR/AppRun"

# Link icon and desktop to root of AppDir (standard requirement)
ln -sf usr/share/icons/hicolor/512x512/apps/sorterr.png "$APP_DIR/sorterr.png"
ln -sf sorterr.desktop "$APP_DIR/default.desktop"

# 2. Download appimagetool if not present
if [ ! -f "appimagetool" ]; then
    echo "[2/4] Downloading appimagetool..."
    curl -L -o appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool
fi

# 3. Build AppImage
echo "[3/4] Packaging AppImage..."
# Use appimagetool from the project root if it exists, or from current scripts dir
[ -f "../appimagetool" ] && TOOL="../appimagetool" || TOOL="./appimagetool"
ARCH=x86_64 $TOOL "$APP_DIR"

# 4. Cleanup
echo "[4/4] Cleanup..."
# rm -rf "$APP_DIR" # Keeping it for now for verification

echo "=== Build Complete: Sorterr-x86_64.AppImage ==="
