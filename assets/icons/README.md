# OpenBoard Application Icons

This directory contains application icons for OpenBoard chess GUI.

## Current Status

The current icon (`openboard.svg`) is a **placeholder** design showing:
- A chess board pattern
- A simplified knight piece
- An accessibility symbol (ear icon)

## Icon Formats

### For Production Use

To create production-ready icons from the SVG source:

#### Linux (PNG)
```bash
# Using Inkscape or ImageMagick
inkscape openboard.svg -w 256 -h 256 -o openboard.png
# or
convert openboard.svg -resize 256x256 openboard.png
```

#### Windows (ICO)
Windows .ico files should contain multiple sizes (16x16, 32x32, 48x48, 256x256):
```bash
# Using ImageMagick
convert openboard.svg -resize 256x256 openboard-256.png
convert openboard.svg -resize 48x48 openboard-48.png
convert openboard.svg -resize 32x32 openboard-32.png
convert openboard.svg -resize 16x16 openboard-16.png
convert openboard-16.png openboard-32.png openboard-48.png openboard-256.png openboard.ico
```

Or use online tools like:
- https://www.icoconverter.com/
- https://convertico.com/

#### macOS (ICNS)
macOS .icns files require an iconset with multiple sizes:
```bash
mkdir openboard.iconset
sips -z 16 16     openboard.svg --out openboard.iconset/icon_16x16.png
sips -z 32 32     openboard.svg --out openboard.iconset/icon_16x16@2x.png
sips -z 32 32     openboard.svg --out openboard.iconset/icon_32x32.png
sips -z 64 64     openboard.svg --out openboard.iconset/icon_32x32@2x.png
sips -z 128 128   openboard.svg --out openboard.iconset/icon_128x128.png
sips -z 256 256   openboard.svg --out openboard.iconset/icon_128x128@2x.png
sips -z 256 256   openboard.svg --out openboard.iconset/icon_256x256.png
sips -z 512 512   openboard.svg --out openboard.iconset/icon_256x256@2x.png
sips -z 512 512   openboard.svg --out openboard.iconset/icon_512x512.png
sips -z 1024 1024 openboard.svg --out openboard.iconset/icon_512x512@2x.png
iconutil -c icns openboard.iconset
```

## Future Improvements

Consider hiring a designer or using design tools to create a professional icon with:
- Better chess piece design (more recognizable knight)
- Clearer accessibility symbolism
- Better color scheme and branding
- Proper shadows and highlights for depth
- Adherence to platform design guidelines (Material Design for Android, Human Interface Guidelines for macOS, etc.)

## License

The placeholder icon is released under the same license as OpenBoard.
