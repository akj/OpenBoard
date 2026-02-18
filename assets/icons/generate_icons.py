#!/usr/bin/env python3
"""
Icon generation script for OpenBoard using Pillow.

Generates platform-specific icon files from the source SVG.
Requires: Pillow (PIL)
"""

import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow not found. Install with: uv sync --group dev")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
SVG_FILE = SCRIPT_DIR / "openboard.svg"

print(f"Generating OpenBoard icons from {SVG_FILE}")

# Check if SVG exists
if not SVG_FILE.exists():
    print(f"Error: openboard.svg not found in {SCRIPT_DIR}")
    sys.exit(1)

# Try to load SVG using Pillow
# Note: Pillow can't directly read SVG, so we need cairosvg or use pre-rendered PNG
# cairosvg provides accurate SVG rendering; Pillow fallback handles missing dependency
try:
    import cairosvg

    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False
    print(
        "Warning: cairosvg not found. Will try to convert SVG using Pillow's limited support"
    )


def svg_to_png(svg_path, png_path, size):
    """Convert SVG to PNG at specified size."""
    if HAS_CAIROSVG:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=size,
            output_height=size,
        )
    else:
        # Fallback: Try to open SVG with Pillow (limited support)
        try:
            img = Image.open(svg_path)
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            img.save(png_path, "PNG")
        except Exception as e:
            print(
                "Error: Cannot convert SVG. Install cairosvg: uv pip install cairosvg"
            )
            print(f"Error details: {e}")
            sys.exit(1)


# Generate PNG for Linux (256x256)
print("Generating PNG for Linux...")
png_file = SCRIPT_DIR / "openboard.png"
svg_to_png(SVG_FILE, png_file, 256)
print(f"  Created: {png_file}")

# Generate ICO for Windows (multi-resolution)
print("Generating ICO for Windows...")
ico_file = SCRIPT_DIR / "openboard.ico"
sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
images = []

for size in sizes:
    temp_path = SCRIPT_DIR / f"temp-{size[0]}.png"
    svg_to_png(SVG_FILE, temp_path, size[0])
    img = Image.open(temp_path)
    images.append(img)
    temp_path.unlink()  # Clean up temp file

# Save as ICO with multiple sizes
images[0].save(
    ico_file,
    format="ICO",
    sizes=[(img.width, img.height) for img in images],
    append_images=images[1:],
)
print(f"  Created: {ico_file}")

# Generate ICNS for macOS
print("Generating ICNS for macOS...")
icns_file = SCRIPT_DIR / "openboard.icns"

# macOS ICNS requires specific sizes
icns_sizes = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

iconset_dir = SCRIPT_DIR / "openboard.iconset"
iconset_dir.mkdir(exist_ok=True)

for size, filename in icns_sizes:
    icon_path = iconset_dir / filename
    svg_to_png(SVG_FILE, icon_path, size)

# Try to use iconutil (macOS only) or pillow_icns
try:
    import subprocess

    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Created: {icns_file}")
    else:
        print("Warning: iconutil failed. Trying Python fallback...")
        raise FileNotFoundError("iconutil not available")
except (FileNotFoundError, subprocess.CalledProcessError):
    # Fallback: Use pillow to create a simple ICNS (not ideal but works)
    print("  Warning: iconutil not available. Creating basic ICNS...")
    # Load the largest PNG
    img_1024 = Image.open(iconset_dir / "icon_512x512@2x.png")
    img_1024.save(icns_file, format="ICNS")
    print(f"  Created: {icns_file} (basic format)")

# Clean up iconset directory
shutil.rmtree(iconset_dir)

print("\nIcon generation complete!")
print("Generated files:")
for icon_file in [png_file, ico_file, icns_file]:
    if icon_file.exists():
        size = icon_file.stat().st_size
        print(f"  {icon_file.name}: {size / 1024:.1f} KB")
