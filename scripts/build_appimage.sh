#!/bin/bash
set -e

# Configuration
APP_NAME="Sorterr-v1.4"
APP_DIR="Sorterr.AppDir"
EXECUTABLE="../dist/Sorterr-v1.4"
ICON="../web/favicon.ico" # Use web favicon as fallback icons if assets is missing

echo "=== Building AppImage for $APP_NAME ==="

# 1. Prepare AppDir
echo "[1/4] Preparing AppDir..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/512x512/apps"

cp "$EXECUTABLE" "$APP_DIR/usr/bin/Sorterr"
if [ -f "$ICON" ]; then
    cp "$ICON" "$APP_DIR/usr/share/icons/hicolor/512x512/apps/sorterr.png"
    cp "$ICON" "$APP_DIR/sorterr.png"
fi

# Create AppRun
cat <<EOF > "$APP_DIR/AppRun"
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
export PATH="\$HERE/usr/bin:\$PATH"
exec Sorterr "\$@"
EOF
chmod +x "$APP_DIR/AppRun"

# Create .desktop if missing
cat <<EOF > "$APP_DIR/sorterr.desktop"
[Desktop Entry]
Type=Application
Name=Sorterr
Exec=Sorterr
Icon=sorterr
Categories=Graphics;
EOF

ln -sf sorterr.desktop "$APP_DIR/default.desktop"

# 2. Download appimagetool if not present
if [ ! -f "appimagetool" ]; then
    echo "[2/4] Downloading appimagetool..."
    curl -L -o appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool
fi

# 3. Build AppImage
echo "[3/4] Packaging AppImage..."
# Use --appimage-extract-and-run for environments without FUSE (like GitHub Actions)
[ -f "../appimagetool" ] && TOOL="../appimagetool" || TOOL="./appimagetool"
ARCH=x86_64 ./appimagetool --appimage-extract-and-run "$APP_DIR" "Sorterr-v1.4-x86_64.AppImage"

# 4. Cleanup
echo "[4/4] Cleanup..."
# rm -rf "$APP_DIR"

echo "=== Build Complete: Sorterr-v1.4-x86_64.AppImage ==="
