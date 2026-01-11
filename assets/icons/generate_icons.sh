#!/bin/bash
# Icon generation script for OpenBoard
#
# This script generates platform-specific icon files from the source SVG.
# Requires: ImageMagick (convert, magick) and optionally Inkscape for better quality

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVG_FILE="$SCRIPT_DIR/openboard.svg"

echo "Generating OpenBoard icons from $SVG_FILE"

# Check if SVG exists
if [ ! -f "$SVG_FILE" ]; then
    echo "Error: openboard.svg not found in $SCRIPT_DIR"
    exit 1
fi

# Generate PNG for Linux (256x256)
echo "Generating PNG for Linux..."
if command -v inkscape &> /dev/null; then
    inkscape "$SVG_FILE" -w 256 -h 256 -o "$SCRIPT_DIR/openboard.png"
elif command -v convert &> /dev/null; then
    convert "$SVG_FILE" -resize 256x256 "$SCRIPT_DIR/openboard.png"
else
    echo "Error: Neither Inkscape nor ImageMagick (convert) found"
    echo "Install with: sudo apt install imagemagick or brew install imagemagick"
    exit 1
fi

# Generate ICO for Windows (multi-resolution)
echo "Generating ICO for Windows..."
if command -v magick &> /dev/null || command -v convert &> /dev/null; then
    # Generate temporary PNGs at different sizes
    convert "$SVG_FILE" -resize 16x16 "$SCRIPT_DIR/temp-16.png"
    convert "$SVG_FILE" -resize 32x32 "$SCRIPT_DIR/temp-32.png"
    convert "$SVG_FILE" -resize 48x48 "$SCRIPT_DIR/temp-48.png"
    convert "$SVG_FILE" -resize 256x256 "$SCRIPT_DIR/temp-256.png"

    # Combine into ICO
    convert "$SCRIPT_DIR/temp-16.png" "$SCRIPT_DIR/temp-32.png" \
            "$SCRIPT_DIR/temp-48.png" "$SCRIPT_DIR/temp-256.png" \
            "$SCRIPT_DIR/openboard.ico"

    # Clean up temp files
    rm "$SCRIPT_DIR/temp-"*.png
else
    echo "Warning: Cannot generate ICO file - ImageMagick not found"
fi

# Generate ICNS for macOS (requires iconutil on macOS)
echo "Generating ICNS for macOS..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    ICONSET_DIR="$SCRIPT_DIR/openboard.iconset"
    mkdir -p "$ICONSET_DIR"

    # Generate all required sizes
    sips -z 16 16     "$SVG_FILE" --out "$ICONSET_DIR/icon_16x16.png" 2>/dev/null || convert "$SVG_FILE" -resize 16x16 "$ICONSET_DIR/icon_16x16.png"
    sips -z 32 32     "$SVG_FILE" --out "$ICONSET_DIR/icon_16x16@2x.png" 2>/dev/null || convert "$SVG_FILE" -resize 32x32 "$ICONSET_DIR/icon_16x16@2x.png"
    sips -z 32 32     "$SVG_FILE" --out "$ICONSET_DIR/icon_32x32.png" 2>/dev/null || convert "$SVG_FILE" -resize 32x32 "$ICONSET_DIR/icon_32x32.png"
    sips -z 64 64     "$SVG_FILE" --out "$ICONSET_DIR/icon_32x32@2x.png" 2>/dev/null || convert "$SVG_FILE" -resize 64x64 "$ICONSET_DIR/icon_32x32@2x.png"
    sips -z 128 128   "$SVG_FILE" --out "$ICONSET_DIR/icon_128x128.png" 2>/dev/null || convert "$SVG_FILE" -resize 128x128 "$ICONSET_DIR/icon_128x128.png"
    sips -z 256 256   "$SVG_FILE" --out "$ICONSET_DIR/icon_128x128@2x.png" 2>/dev/null || convert "$SVG_FILE" -resize 256x256 "$ICONSET_DIR/icon_128x128@2x.png"
    sips -z 256 256   "$SVG_FILE" --out "$ICONSET_DIR/icon_256x256.png" 2>/dev/null || convert "$SVG_FILE" -resize 256x256 "$ICONSET_DIR/icon_256x256.png"
    sips -z 512 512   "$SVG_FILE" --out "$ICONSET_DIR/icon_256x256@2x.png" 2>/dev/null || convert "$SVG_FILE" -resize 512x512 "$ICONSET_DIR/icon_256x256@2x.png"
    sips -z 512 512   "$SVG_FILE" --out "$ICONSET_DIR/icon_512x512.png" 2>/dev/null || convert "$SVG_FILE" -resize 512x512 "$ICONSET_DIR/icon_512x512.png"
    sips -z 1024 1024 "$SVG_FILE" --out "$ICONSET_DIR/icon_512x512@2x.png" 2>/dev/null || convert "$SVG_FILE" -resize 1024x1024 "$ICONSET_DIR/icon_512x512@2x.png"

    # Create ICNS
    iconutil -c icns "$ICONSET_DIR" -o "$SCRIPT_DIR/openboard.icns"

    # Clean up iconset directory
    rm -rf "$ICONSET_DIR"
else
    echo "Warning: ICNS generation requires macOS (iconutil)"
    echo "You can generate ICNS manually or use an online converter"
fi

echo ""
echo "Icon generation complete!"
echo "Generated files:"
ls -lh "$SCRIPT_DIR"/*.{png,ico,icns} 2>/dev/null || true
