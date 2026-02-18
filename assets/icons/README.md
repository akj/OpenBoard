# OpenBoard Application Icons

This directory contains application icons for OpenBoard chess GUI.

## Current Status

The current icon (`openboard.svg`) is a **placeholder** design showing:
- A chess board pattern
- A simplified knight piece
- An accessibility symbol (ear icon)

## Icon Generation

Two generation scripts produce `openboard.ico` (Windows), `openboard.icns` (macOS), and `openboard.png` (Linux) from `openboard.svg`. Do not edit the generated files directly.

### Python (generate_icons.py)

Requires Pillow (included in dev dependencies). Uses cairosvg if available for accurate SVG rendering; falls back to Pillow's limited SVG support.

```bash
uv run python assets/icons/generate_icons.py
```

### Shell (generate_icons.sh)

Requires Inkscape or ImageMagick and `iconutil` (macOS only for ICNS).

```bash
bash assets/icons/generate_icons.sh
```

## Icon Formats

### Linux (PNG)

256x256 PNG for window manager and desktop integration.

### Windows (ICO)

Multi-resolution ICO containing 16x16, 32x32, 48x48, and 256x256 sizes.

### macOS (ICNS)

Full iconset with 10 sizes from 16x16 to 1024x1024 (512x512@2x).

## License

The placeholder icon is released under the same license as OpenBoard.
