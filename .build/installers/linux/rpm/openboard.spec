Name:           openboard
Version:        {VERSION}
Release:        1%{?dist}
Summary:        Accessible chess GUI with screen reader support

License:        MIT
URL:            https://github.com/openboard/openboard
Source0:        %{name}-%{version}.tar.gz

# Runtime dependencies
Requires:       gtk3
Requires:       speech-dispatcher >= 0.8
Requires:       espeak-ng

BuildArch:      x86_64

%description
OpenBoard is an accessible, cross-platform chess GUI written in Python.
It uses wxPython for the GUI and provides keyboard navigation, screen
reader support, and UCI engine integration (specifically Stockfish).

Features:
 * Full keyboard navigation
 * Screen reader support via accessible-output3
 * UCI chess engine support (Stockfish)
 * Human vs Human, Human vs Computer, and Computer vs Computer modes
 * Multiple difficulty levels

%prep
# No prep needed - binary distribution

%build
# No build needed - binary distribution

%install
# Create directory structure
mkdir -p %{buildroot}/opt/openboard
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps

# Copy application files (will be done by build script)
# cp -r OpenBoard/* %{buildroot}/opt/openboard/

# Install desktop file
install -D -m 644 openboard.desktop %{buildroot}/usr/share/applications/openboard.desktop

# Install icon (if available)
# install -D -m 644 openboard.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/openboard.png

%files
/opt/openboard/*
/usr/share/applications/openboard.desktop
# /usr/share/icons/hicolor/256x256/apps/openboard.png

%post
# Update desktop database
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications &> /dev/null || :
fi

# Update icon cache
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor &> /dev/null || :
fi

# Update MIME database
if [ -x /usr/bin/update-mime-database ]; then
    /usr/bin/update-mime-database /usr/share/mime &> /dev/null || :
fi

%postun
# Clean up after uninstall
if [ $1 -eq 0 ]; then
    if [ -x /usr/bin/update-desktop-database ]; then
        /usr/bin/update-desktop-database -q /usr/share/applications &> /dev/null || :
    fi
    if [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor &> /dev/null || :
    fi
fi

%changelog
* Tue Dec 10 2024 OpenBoard Project <team@openboard.org> - {VERSION}-1
- Initial RPM release
