# Building installers

Install the locked environment with `uv sync --locked`, then build the executable
with `uv run --no-sync python .build/scripts/build.py`.
The executable build goes into `dist/OpenBoard` on Windows and Linux or
`dist/OpenBoard.app` on macOS.

Run `uv run --no-sync python .build/installers/scripts/build_installer.py` on the
target operating system. Installers go into `dist/installers`.

Windows needs Inno Setup. macOS uses its built-in `hdiutil` tool.
Linux needs `dpkg-deb` for DEB packages and `rpmbuild` for RPM packages.
A requested installer that cannot be built fails the command.

Use `--type innosetup`, `--type dmg`, `--type deb`, or `--type deb,rpm` to choose the
platform's output. `--dist-dir` and `--output-dir` accept alternate build directories.
The default version comes from `[project].version` in `pyproject.toml`.

Validate a packaged executable with
`uv run --no-sync python .build/validation/verify_build.py --executable <path>`.
For macOS, pass the executable inside `OpenBoard.app/Contents/MacOS/OpenBoard`.
The startup smoke check loads bundled modules and makes a chess move without opening
a window or speaking. Installer creation and startup checks do not establish live
screen reader behavior.

The release workflow requires every installer and archive, runs packaged startup
checks, and hashes the downloadable files into `SHA256SUMS`.
