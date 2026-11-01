# Run, test, and package GraphCad

GraphCad 1.1.0 is a native Python 3.12 / Qt 6.10 desktop application. Use a 64-bit Python installation matching the target operating system and architecture. Dependency installation requires an accessible package source or a previously downloaded wheel directory; ordinary application use is offline.

The current build targets Windows 11 x64 and macOS 14+. Qt 6.10 also supports Windows 10 version 1809+, but that does not establish a tested GraphCad Windows release. The tested Apple Silicon NumPy wheel requires macOS 14, while PySide6 itself supports macOS 13. Windows and Intel macOS binaries must be built and tested on their respective platforms. This delivery does not claim those builds were executed on the macOS Apple Silicon host. There is no cross-compilation or universal-binary claim.

## Windows 11

See [the complete Windows 11 x64 instructions](WINDOWS11.md) for official prerequisites, exact PowerShell commands, native package validation, installer creation, upgrades, and troubleshooting. In brief, from the project root with the official Python install manager:

```powershell
py install 3.12
py -V:3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe run_graphcad.py
```

The PySide6 wheels contain Qt and PyInstaller supplies a prebuilt bootloader. This route does not require Visual Studio, a compiler, CMake, or a Qt SDK. These would be needed only for deliberately compiling the native dependencies or bootloader from source. The wheel-only installation flag stops if a suitable binary is unavailable.

## macOS source run

Use Python 3.12 matching the machine architecture (`arm64` for Apple Silicon or `x86_64` for Intel):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python run_graphcad.py
```

For a particular document, append its path. `run_graphite.py`, the `graphite` package, and `.graphite` files remain compatible. Do not mix Intel and Apple Silicon libraries in one build environment.

## Automated checks

In subsequent commands, `python` means the environment executable: `.venv/bin/python` on macOS, or `.\.venv\Scripts\python.exe` on Windows.

```sh
python -m pip install --only-binary=:all: -r requirements-dev.txt
python -m pytest -q
python run_graphcad.py --smoke-test
```

Qt interaction tests set `QT_QPA_PLATFORM=offscreen`. The smoke test opens the native window then exits after one second; set the same environment variable to run it without a display. PyMuPDF inspects PDF output in development tests and is excluded from the application bundle. The actual executed checks and platform limits belong in [TEST_RESULTS.md](TEST_RESULTS.md).

## Build native bundles

After installing development requirements, build on the target OS:

```sh
python scripts/build.py --test
```

The script uses `GraphCad.spec` and produces:

| Target | Output |
|---|---|
| Windows x64 | `dist/GraphCad/GraphCad.exe` and adjacent `_internal/` libraries |
| macOS native architecture | `dist/GraphCad.app`, plus intermediate `dist/GraphCad/` |

Keep the complete Windows application folder together. The separate library layout keeps Qt replaceable and avoids a self-extracting one-file executable. Build work, generated icons, collected notices, and PyInstaller cache default to `../../work/graphcad-pyinstaller/`; use `--work PATH` and `--dist PATH` to override. For example, `python scripts/build.py --work build-work` keeps intermediates in the project.

The application icon is generated from `packaging/icon.svg`. Windows executables carry GraphCad 1.1.0 version metadata. The original macOS bundle ID `io.graphite.editor` is retained for document-association compatibility.

## Verify the packaged application

```sh
# macOS
dist/GraphCad.app/Contents/MacOS/GraphCad --smoke-test
dist/GraphCad.app/Contents/MacOS/GraphCad --verify-build /tmp/graphcad-verification
```

For Windows, the PowerShell `Start-Process -Wait -PassThru` example in [WINDOWS11.md](WINDOWS11.md) captures the exit status of the GUI executable reliably.

`--verify-build DIRECTORY` writes an editable sample, PNG/PDF/SVG/DXF files, and `verification.json`, then verifies the installed bundle's document roundtrip and native output dependencies. A failure produces a failing exit status. This is additional evidence beyond startup, while interaction tests and manual target-platform checks cover the editing UI. It does not verify an unavailable DWG converter or every printer/CAD application.

## macOS disk image and release signing

```sh
sh packaging/make_dmg.sh
```

This creates `dist/GraphCad-1.1.0-macOS-arm64.dmg` or `dist/GraphCad-1.1.0-macOS-x86_64.dmg`, containing GraphCad.app and an Applications shortcut. Drag the app into Applications. The developer bundle is ad hoc signed by PyInstaller; it has no Developer ID identity or notarization, and the disk image is unsigned. System or organizational security policy may require explicit approval to open a downloaded developer build.

For a release, supply your own Apple Developer ID and notarization credentials. Set `GRAPHCAD_CODESIGN_IDENTITY` before building; `GRAPHITE_CODESIGN_IDENTITY` remains a fallback. Then verify the app, build the DMG, and submit it to Apple:

```sh
codesign --verify --deep --strict --verbose=2 dist/GraphCad.app
sh packaging/make_dmg.sh
xcrun notarytool submit dist/GraphCad-1.1.0-macOS-arm64.dmg --keychain-profile YOUR_PROFILE --wait
xcrun stapler staple dist/GraphCad-1.1.0-macOS-arm64.dmg
```

Use the actual architecture filename. Developer ID signing/notarization were not performed for this delivery. Review Apple's and PyInstaller's current hardened-runtime guidance for your release channel; the project does not bypass operating-system security.

## Windows installer

Build the Windows application folder first. Install [Inno Setup 6](https://jrsoftware.org/isdl.php#v6), then run:

```powershell
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '.\packaging\windows.iss'
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed: $LASTEXITCODE" }
```

The output is `dist/GraphCad-1.1.0-Windows-x64-Setup.exe`. The installer is per user and retains the prior AppId and `Graphite.Document` registry identity for upgrades. It replaces the old application shortcut/executable names while preserving user documents. Actual Windows installer execution and upgrade validation must be performed on Windows. See [WINDOWS11.md](WINDOWS11.md) for exact validation and optional signing steps.

## Continuous integration and offline use

`.github/workflows/build.yml` runs tests, builds and verifies native Windows x64 and macOS Apple Silicon/Intel bundles independently, and uploads the artifacts. It pins the official Inno Setup 6.7.4 installer rather than assuming the latest release installs to the version-6 folder. The workflow is provided for the root of a repository containing this source; it was not dispatched here. GitHub runner availability can change; consult the [official runner catalog](https://github.com/actions/runner-images).

For an offline target, use a connected machine with the same OS, Python version, and architecture to download `python -m pip download --only-binary=:all: -r requirements-dev.txt -d wheels`. Copy the source and wheels, create the environment, then install with `python -m pip install --no-index --find-links wheels -r requirements-dev.txt`. Packaged application users do not need Python or these build tools.

## Compatibility and notices

Public artifact names and launcher commands use GraphCad. The internal Python package, `.graphite` JSON format/version, macOS bundle ID, installer upgrade identity, and legacy launcher remain stable. New `GRAPHCAD_LICENSE_DIR`, `GRAPHCAD_ICON`, and `GRAPHCAD_CODESIGN_IDENTITY` build settings take precedence over their legacy `GRAPHITE_*` equivalents. Dependency licenses and the original MIT copyright notice are retained; see [LICENSES.md](LICENSES.md).
