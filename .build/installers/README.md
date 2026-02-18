# OpenBoard Installer Build System

## Overview

This directory contains the infrastructure for building professional, platform-specific installers for OpenBoard. The installer system provides a streamlined, user-friendly installation experience across Windows, macOS, and Linux platforms.

### Supported Installer Types

- **Windows**: Inno Setup installer (.exe) with Start Menu integration, desktop shortcuts, and file associations
- **macOS**: DMG disk image with drag-to-Applications installation
- **Linux**: Native package formats
  - DEB packages for Debian/Ubuntu distributions
  - RPM packages for Fedora/RHEL distributions

### Benefits Over Portable Archives

While portable archives provide flexibility for advanced users, platform-native installers offer several advantages:

- **Automated dependency installation**: Package managers handle runtime dependencies
- **System integration**: Start Menu entries, desktop shortcuts, and file associations
- **Update management**: Integration with native package managers enables easier updates
- **Uninstallation**: Clean removal through system-native uninstallers
- **Security**: Code signing and package verification (planned future enhancement)
- **User experience**: Familiar installation workflows for end users

## Quick Start

```bash
# Build all installer types for current platform
uv run python .build/installers/scripts/build_installer.py

# Build specific installer type
uv run python .build/installers/scripts/build_installer.py --type deb

# Build with custom version
uv run python .build/installers/scripts/build_installer.py --version 1.0.0

# Enable verbose logging
uv run python .build/installers/scripts/build_installer.py --verbose
```

## Architecture

### Directory Structure

```
.build/installers/
├── README.md                  # This file
├── scripts/                   # Build orchestration scripts
│   ├── build_installer.py     # Main entry point
│   ├── windows_installer.py   # Windows Inno Setup builder
│   ├── macos_installer.py     # macOS DMG builder
│   └── linux_installer.py     # Linux DEB/RPM builder
├── windows/                   # Windows-specific configuration
│   └── innosetup.iss          # Inno Setup script
├── macos/                     # macOS-specific configuration
│   └── (DMG customization files - future)
└── linux/                     # Linux-specific configuration
    ├── debian/                # DEB package templates
    │   ├── DEBIAN/
    │   │   ├── control        # Package metadata
    │   │   └── postinst       # Post-installation script
    │   └── openboard.desktop  # Desktop entry file
    └── rpm/                   # RPM package templates
        ├── openboard.spec     # RPM spec file
        └── openboard.desktop  # Desktop entry file
```

### Platform-Specific Builders

Each platform has a dedicated builder module that encapsulates platform-specific packaging logic:

- **`windows_installer.py`**: Uses Inno Setup compiler (iscc.exe) to build Windows installers
- **`macos_installer.py`**: Creates DMG disk images using create-dmg or hdiutil
- **`linux_installer.py`**: Builds DEB packages with dpkg-deb and RPM packages with rpmbuild

The main orchestrator (`build_installer.py`) detects the current platform, reads version from `pyproject.toml`, and delegates to the appropriate builder.

### Workflow Integration

The installer build system integrates with the GitHub Actions CI/CD pipeline:

1. **Build Stage**: PyInstaller creates platform-specific executables
2. **Validation Stage**: Executables are validated for correct operation
3. **Installer Stage**: Validated builds are packaged into platform-native installers
4. **Release Stage**: Installers are attached to GitHub releases

See [`.github/workflows/release.yml`](../../.github/workflows/release.yml) for the complete workflow.

## Building Installers Locally

### Prerequisites

#### All Platforms
- Python 3.12 or later
- uv package manager
- Completed PyInstaller build (run `uv run python -m PyInstaller openboard.spec` first)

#### Windows
- **Inno Setup 6** or later
  - Download from: https://jrsoftware.org/isdl.php
  - Install to default location or ensure `iscc.exe` is in PATH
  - Common locations checked automatically:
    - `C:\Program Files (x86)\Inno Setup 6\iscc.exe`
    - `C:\Program Files\Inno Setup 6\iscc.exe`

#### macOS
- **Built-in tools**: hdiutil (included with macOS)
- **Optional**: create-dmg for enhanced DMG customization
  ```bash
  brew install create-dmg
  ```

#### Linux (Debian/Ubuntu)
- **DEB packages**:
  ```bash
  sudo apt install dpkg
  ```
- **RPM packages** (optional):
  ```bash
  sudo apt install rpm
  ```

#### Linux (Fedora/RHEL)
- **RPM packages**:
  ```bash
  sudo dnf install rpm-build
  ```
- **DEB packages** (optional):
  ```bash
  sudo dnf install dpkg
  ```

### Command-Line Usage

The build script accepts several options for customization:

```bash
# Basic usage - builds all installers for current platform
uv run python .build/installers/scripts/build_installer.py

# Specify version (otherwise reads from pyproject.toml)
uv run python .build/installers/scripts/build_installer.py --version 1.0.0

# Build specific installer types
uv run python .build/installers/scripts/build_installer.py --type deb        # DEB only
uv run python .build/installers/scripts/build_installer.py --type rpm        # RPM only
uv run python .build/installers/scripts/build_installer.py --type deb,rpm    # Both

# Custom directories
uv run python .build/installers/scripts/build_installer.py \
  --dist-dir /path/to/dist \
  --output-dir /path/to/output

# Verbose logging for debugging
uv run python .build/installers/scripts/build_installer.py --verbose
```

### Platform-Specific Instructions

#### Windows

1. **Install Inno Setup**:
   - Download from https://jrsoftware.org/isdl.php
   - Run installer and accept default settings

2. **Build PyInstaller executable**:
   ```cmd
   uv run python -m PyInstaller openboard.spec
   ```

3. **Build installer**:
   ```cmd
   uv run python .build/installers/scripts/build_installer.py
   ```

4. **Output location**:
   - Installer: `dist/installers/OpenBoard-v{version}-windows-x64-setup.exe`

5. **Test installation**:
   ```cmd
   dist\installers\OpenBoard-v{version}-windows-x64-setup.exe
   ```

#### macOS

1. **(Optional) Install create-dmg**:
   ```bash
   brew install create-dmg
   ```

2. **Build PyInstaller .app bundle**:
   ```bash
   uv run python -m PyInstaller openboard.spec
   ```

3. **Build DMG**:
   ```bash
   uv run python .build/installers/scripts/build_installer.py
   ```

4. **Output location**:
   - DMG: `dist/installers/OpenBoard-v{version}-macos-x64.dmg`

5. **Test installation**:
   ```bash
   open dist/installers/OpenBoard-v{version}-macos-x64.dmg
   ```

#### Linux

1. **Install packaging tools**:
   ```bash
   # Debian/Ubuntu
   sudo apt install dpkg rpm

   # Fedora/RHEL
   sudo dnf install rpm-build dpkg
   ```

2. **Build PyInstaller executable**:
   ```bash
   uv run python -m PyInstaller openboard.spec
   ```

3. **Build packages**:
   ```bash
   # Build both DEB and RPM
   uv run python .build/installers/scripts/build_installer.py

   # Or build individually
   uv run python .build/installers/scripts/build_installer.py --type deb
   uv run python .build/installers/scripts/build_installer.py --type rpm
   ```

4. **Output locations**:
   - DEB: `dist/installers/openboard_{version}_amd64.deb`
   - RPM: `dist/installers/openboard-{version}-1.x86_64.rpm`

5. **Test installation**:
   ```bash
   # DEB
   sudo dpkg -i dist/installers/openboard_{version}_amd64.deb
   sudo apt-get install -f  # Install dependencies

   # RPM
   sudo rpm -ivh dist/installers/openboard-{version}-1.x86_64.rpm
   ```

## Installer Configurations

### Windows: Inno Setup Script

Configuration file: [`windows/innosetup.iss`](windows/innosetup.iss)

#### Key Sections

**Setup Configuration**:
```pascal
[Setup]
AppId={{B8F3C4E5-9A2D-4F1B-8C6E-7D3A5B9F2E1C}  # Unique application ID
AppName={#AppName}
AppVersion={#AppVersion}                        # Injected at build time
DefaultDirName={autopf}\{#AppName}              # Program Files location
PrivilegesRequired=admin                        # Requires admin for installation
```

**Installation Tasks**:
```pascal
[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"
Name: "pgnassociation"; Description: "Associate .PGN files with OpenBoard"
```

**File Associations** (optional, user-selectable):
```pascal
[Registry]
Root: HKA; Subkey: "Software\Classes\.pgn"; ValueData: "OpenBoardPGN"
Root: HKA; Subkey: "Software\Classes\OpenBoardPGN\shell\open\command";
  ValueData: """{app}\OpenBoard.exe"" ""%1"""
```

#### Customization

Edit `windows/innosetup.iss` to customize:
- Application metadata (AppPublisher, AppURL)
- Installation directory defaults
- Optional tasks (desktop icons, file associations)
- Post-installation actions
- Uninstaller behavior

### macOS: DMG Creation

Builder: [`scripts/macos_installer.py`](scripts/macos_installer.py)

#### DMG Features

- Volume name: "OpenBoard {version}"
- Drag-to-Applications symlink for easy installation
- Compressed format (UDZO) for smaller download size
- Falls back to hdiutil if create-dmg unavailable

#### Customization Options

**Using create-dmg** (enhanced):
```python
command = [
    "create-dmg",
    "--volname", volume_name,
    "--window-size", "600", "400",     # Window dimensions
    "--icon-size", "80",                # Icon size
    "--app-drop-link", "400", "200",    # Applications symlink position
    str(dmg_path),
    str(app_bundle)
]
```

**Future enhancements**:
- Custom background images
- Custom icon positioning
- License agreement display

### Linux: DEB Package Metadata

Configuration files:
- [`linux/debian/DEBIAN/control`](linux/debian/DEBIAN/control)
- [`linux/debian/DEBIAN/postinst`](linux/debian/DEBIAN/postinst)
- [`linux/debian/openboard.desktop`](linux/debian/openboard.desktop)

#### Control File

Defines package metadata and dependencies:
```
Package: openboard
Version: {VERSION}                    # Replaced at build time
Section: games
Architecture: amd64
Depends: libgtk-3-0, speech-dispatcher (>= 0.8), espeak-ng
Description: Accessible chess GUI with screen reader support
```

#### Post-Installation Script

Executes after package installation:
```bash
#!/bin/bash
# Update desktop database
update-desktop-database -q /usr/share/applications

# Update icon cache
gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor

# Update MIME database
update-mime-database /usr/share/mime
```

#### Desktop Entry

Integrates with desktop environment:
```ini
[Desktop Entry]
Name=OpenBoard
Exec=/opt/openboard/OpenBoard
Icon=openboard
Categories=Game;BoardGame;
MimeType=application/x-chess-pgn;
Keywords=chess;game;stockfish;accessible;
```

### Linux: RPM Package Specification

Configuration file: [`linux/rpm/openboard.spec`](linux/rpm/openboard.spec)

#### Key Sections

**Package Metadata**:
```spec
Name:           openboard
Version:        {VERSION}
Release:        1%{?dist}
Summary:        Accessible chess GUI with screen reader support
License:        MIT
Requires:       gtk3, speech-dispatcher >= 0.8, espeak-ng
BuildArch:      x86_64
```

**Post-Installation Scripts**:
```spec
%post
# Update desktop database
update-desktop-database -q /usr/share/applications

# Update icon cache
gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor
```

#### Customization

Edit `linux/rpm/openboard.spec` to modify:
- Package dependencies
- Installation directories
- Post-install/pre-uninstall scripts
- Package metadata (license, URL, description)

## GitHub Actions Integration

### Release Workflow Overview

The release workflow ([`.github/workflows/release.yml`](../../.github/workflows/release.yml)) is triggered on version tags (e.g., `v1.0.0`) and performs the following stages:

1. **Build Stage**: Builds PyInstaller executables for all platforms
2. **Validation Stage**: Validates executables can launch successfully
3. **Installer Stage**: Packages validated builds into platform-native installers
4. **Release Stage**: Creates GitHub release with all artifacts

### Installer Build Jobs

Three parallel installer build jobs run after validation:

```yaml
build-installer-linux:
  uses: ./.github/workflows/setup-build-installer.yml
  with:
    os: ubuntu-latest
    artifact-name: openboard-linux
    installer-type: deb,rpm

build-installer-macos:
  uses: ./.github/workflows/setup-build-installer.yml
  with:
    os: macos-latest
    artifact-name: openboard-macos
    installer-type: dmg

build-installer-windows:
  uses: ./.github/workflows/setup-build-installer.yml
  with:
    os: windows-latest
    artifact-name: openboard-windows
    installer-type: innosetup
```

### Artifact Handling

Each installer build job:
1. Downloads the platform-specific PyInstaller build artifact
2. Extracts version from the git tag
3. Runs the appropriate installer builder
4. Uploads the resulting installer as a GitHub Actions artifact
5. The release job downloads all artifacts and attaches them to the GitHub release

### Release Assets

The GitHub release includes:
- Platform-native installers (recommended for end users)
- Portable archives (for advanced users)
- SHA256 checksums for verification

## Customization Guide

### Changing Installer Branding

#### Application Name and Publisher

**Windows** (`windows/innosetup.iss`):
```pascal
#define AppName "OpenBoard"
#define AppPublisher "OpenBoard Project"
#define AppURL "https://github.com/yourusername/openboard"
```

**Linux DEB** (`linux/debian/DEBIAN/control`):
```
Package: openboard
Maintainer: OpenBoard Project <noreply@example.com>
Homepage: https://github.com/yourusername/openboard
```

**Linux RPM** (`linux/rpm/openboard.spec`):
```spec
Name:           openboard
URL:            https://github.com/yourusername/openboard
```

**Desktop Files** (`linux/debian/openboard.desktop`, `linux/rpm/openboard.desktop`):
```ini
[Desktop Entry]
Name=OpenBoard
GenericName=Chess GUI
Comment=Accessible chess game with screen reader support
```

#### Application Icons

**Windows**:
- Add icon file to PyInstaller build
- Update `UninstallDisplayIcon` in `innosetup.iss`

**macOS**:
- Set icon in PyInstaller spec file (`openboard.spec`)
- Icon automatically included in .app bundle

**Linux**:
- Add icon files to `linux/icons/` directory
- Update `openboard.desktop` Icon field
- Copy icon in installer build scripts

### Modifying File Associations

#### Windows: PGN File Association

Edit `windows/innosetup.iss`:

```pascal
[Tasks]
Name: "pgnassociation"; Description: "Associate .PGN files with OpenBoard"

[Registry]
# Register .pgn extension
Root: HKA; Subkey: "Software\Classes\.pgn";
  ValueData: "OpenBoardPGN";
  Tasks: pgnassociation

# Register application handler
Root: HKA; Subkey: "Software\Classes\OpenBoardPGN\shell\open\command";
  ValueData: """{app}\OpenBoard.exe"" ""%1""";
  Tasks: pgnassociation
```

#### Linux: MIME Type Association

Edit `linux/debian/openboard.desktop` and `linux/rpm/openboard.desktop`:

```ini
[Desktop Entry]
MimeType=application/x-chess-pgn;application/vnd.chess-pgn;
```

### Adding Custom Install Scripts

#### Windows: Post-Installation Actions

Edit `windows/innosetup.iss`:

```pascal
[Run]
# Launch application after installation
Filename: "{app}\OpenBoard.exe";
  Description: "Launch OpenBoard";
  Flags: nowait postinstall skipifsilent

# Open documentation
Filename: "{app}\README.html";
  Description: "View documentation";
  Flags: shellexec postinstall skipifsilent unchecked
```

#### Linux: Post-Installation Scripts

**DEB** - Edit `linux/debian/DEBIAN/postinst`:
```bash
#!/bin/bash
set -e

# Update desktop database
if [ -x /usr/bin/update-desktop-database ]; then
    update-desktop-database -q /usr/share/applications
fi

# Custom setup logic
echo "OpenBoard installed successfully"
```

**RPM** - Edit `linux/rpm/openboard.spec`:
```spec
%post
# Update desktop database
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications &> /dev/null || :
fi

# Custom setup logic
echo "OpenBoard installed successfully"
```

### Modifying Installation Directories

#### Windows

Edit `windows/innosetup.iss`:
```pascal
[Setup]
DefaultDirName={autopf}\OpenBoard      # Program Files
# Or for user-local installation:
# DefaultDirName={userpf}\OpenBoard    # User's Program Files
```

#### Linux

**DEB** - Edit `linux/debian/DEBIAN/control` and adjust paths in `scripts/linux_installer.py`:
```python
opt_dir = temp_dir / "opt" / "openboard"          # Current
# Or use /usr/local:
# usr_local_dir = temp_dir / "usr" / "local" / "bin"
```

**RPM** - Edit `linux/rpm/openboard.spec`:
```spec
%install
mkdir -p %{buildroot}/opt/openboard
# Or use /usr/local:
# mkdir -p %{buildroot}/usr/local/bin
```

## Troubleshooting

### Common Build Errors

#### Error: "PyInstaller distribution directory not found"

**Cause**: PyInstaller build hasn't been run or completed successfully.

**Solution**:
```bash
# Run PyInstaller build first
uv run python -m PyInstaller openboard.spec

# Verify dist directory exists
ls -la dist/OpenBoard/  # Linux/macOS
dir dist\OpenBoard\     # Windows
```

#### Error: "Version not found in pyproject.toml"

**Cause**: `pyproject.toml` missing or malformed.

**Solution**:
```bash
# Verify pyproject.toml exists
cat pyproject.toml | grep version

# Or specify version explicitly
uv run python .build/installers/scripts/build_installer.py --version 1.0.0
```

### Platform-Specific Issues

#### Windows: "Inno Setup compiler not found"

**Cause**: Inno Setup not installed or not in PATH.

**Solutions**:
1. Install Inno Setup from https://jrsoftware.org/isdl.php
2. Add Inno Setup directory to system PATH
3. Install to default location (automatically detected)

**Verify installation**:
```cmd
iscc /?
```

#### macOS: "OSError: must be run on macOS"

**Cause**: Attempting to build macOS DMG on non-macOS platform.

**Solution**: DMG creation requires macOS. Use GitHub Actions or build on macOS hardware.

#### Linux: "dpkg-deb not found"

**Cause**: dpkg not installed.

**Solution**:
```bash
# Debian/Ubuntu
sudo apt install dpkg

# Fedora/RHEL
sudo dnf install dpkg
```

#### Linux: "rpmbuild not found"

**Cause**: rpm-build not installed (RPM creation is optional).

**Solution**:
```bash
# Debian/Ubuntu
sudo apt install rpm

# Fedora/RHEL
sudo dnf install rpm-build
```

**Note**: RPM build will be skipped if rpmbuild is unavailable. This is expected behavior on Debian-based systems.

### Debugging Tips

#### Enable Verbose Logging

```bash
uv run python .build/installers/scripts/build_installer.py --verbose
```

This provides detailed output including:
- File paths being used
- External command execution
- Step-by-step build progress
- Error stack traces

#### Check Build Artifacts

Verify intermediate build artifacts:

```bash
# Check PyInstaller output
ls -la dist/OpenBoard/          # Linux/macOS
dir dist\OpenBoard\             # Windows

# Check installer output
ls -la dist/installers/         # Linux/macOS
dir dist\installers\            # Windows
```

#### Test Installers in Virtual Machines

For thorough testing:
1. Use VirtualBox or VMware for cross-platform testing
2. Test installation on clean OS installations
3. Verify uninstallation leaves no artifacts
4. Check system integration (Start Menu, desktop shortcuts, file associations)

#### Validate Package Contents

**DEB packages**:
```bash
dpkg --contents openboard_{version}_amd64.deb
dpkg --info openboard_{version}_amd64.deb
```

**RPM packages**:
```bash
rpm -qlp openboard-{version}-1.x86_64.rpm
rpm -qip openboard-{version}-1.x86_64.rpm
```

**Windows installers**:
- Run installer with `/LOG="install.log"` flag
- Review log file for installation details

#### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Missing dependencies in package | Not specified in control/spec | Add to `Depends:`/`Requires:` field |
| Desktop file not showing | Desktop database not updated | Ensure postinst script runs correctly |
| File permissions incorrect | chmod not set properly | Check executable permissions in build script |
| Installer size too large | Uncompressed or debug symbols | Verify PyInstaller strip/compression settings |
| Version mismatch | Hardcoded version in templates | Use `{VERSION}` placeholder in all templates |

## Maintenance

### Updating Dependencies

When package dependencies change:

1. **Update PyInstaller build** (`openboard.spec`)
2. **Update DEB control file** (`linux/debian/DEBIAN/control`):
   ```
   Depends: libgtk-3-0, speech-dispatcher (>= 0.8), espeak-ng, new-dependency
   ```
3. **Update RPM spec file** (`linux/rpm/openboard.spec`):
   ```spec
   Requires: gtk3, speech-dispatcher >= 0.8, espeak-ng, new-dependency
   ```
4. **Update documentation** (this README and release notes)
5. **Test installation** on clean systems to verify dependency resolution

### Version Management

Version is automatically read from `pyproject.toml`:

```toml
[project]
name = "openboard"
version = "0.1.0"  # Update this
```

To override for testing:
```bash
uv run python .build/installers/scripts/build_installer.py --version 1.0.0-beta
```

**Version string replacement** happens automatically in:
- Windows: `AppVersion` in Inno Setup script
- macOS: DMG volume name
- Linux: `Version` field in DEB control and RPM spec files

### Testing Installers

#### Pre-Release Testing Checklist

- [ ] Build installers for all platforms
- [ ] Install on clean OS installations
- [ ] Verify application launches successfully
- [ ] Check desktop integration (icons, menus, shortcuts)
- [ ] Test file associations (if enabled)
- [ ] Verify dependencies are installed correctly
- [ ] Test uninstallation removes all files
- [ ] Validate SHA256 checksums match
- [ ] Test upgrade from previous version (if applicable)

#### Automated Testing

The GitHub Actions workflow includes:
- Executable validation before installer creation
- Checksum generation for verification
- Cross-platform build testing

For local testing:
```bash
# Build and validate
uv run python -m PyInstaller openboard.spec
uv run python .build/validation/verify_build.py
uv run python .build/installers/scripts/build_installer.py
```

#### Manual Testing Recommendations

1. **Clean Installation**: Test on fresh OS install or VM
2. **Upgrade Path**: Test upgrading from previous version
3. **Uninstallation**: Verify clean removal of all files
4. **Permissions**: Test without admin rights (where applicable)
5. **Dependencies**: Test on system without pre-installed dependencies
6. **File Associations**: Open associated files, verify correct application launches
7. **Accessibility**: Test with screen readers enabled

### Continuous Integration

The installer build system is integrated into the GitHub Actions release workflow:

**Triggering a release**:
```bash
# Create and push version tag
git tag v1.0.0
git push origin v1.0.0
```

**Workflow stages**:
1. Builds executables for all platforms
2. Validates executables work correctly
3. Builds installers from validated executables
4. Creates GitHub release with all artifacts

**Monitoring builds**:
- View progress: https://github.com/{user}/{repo}/actions
- Download artifacts from completed builds
- Check logs for build failures

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [Inno Setup Documentation](https://jrsoftware.org/ishelp/)
- [Debian Package Guidelines](https://www.debian.org/doc/debian-policy/)
- [RPM Packaging Guide](https://rpm-packaging-guide.github.io/)
- [freedesktop.org Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/)

## Contributing

When modifying the installer system:

1. Test changes on all supported platforms (or in CI)
2. Update this documentation to reflect changes
3. Verify installers work on clean OS installations
4. Update GitHub Actions workflows if necessary
5. Test upgrade paths from previous versions

For questions or issues, open an issue on the GitHub repository.
