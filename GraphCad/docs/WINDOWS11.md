# GraphCad on Windows 11 x64

This guide runs the source, builds a complete desktop application folder, and creates an optional installer. The configuration targets Windows 11 on an Intel/AMD 64-bit PC. The project has not been built or tested on Windows in the supplied macOS environment; these are reproducible instructions, not a claim that a Windows binary has already passed validation.

## 1. Choose an installer or the source

If your release includes `GraphCad-1.1.0-Windows-x64-Setup.exe`, run that installer. It installs for the current user and offers a Start-menu shortcut. An installed GraphCad does not need a separate Python installation, Visual Studio, Qt SDK, or internet connection for ordinary editing and exports. Keep editable diagrams as `.graphite` projects.

If no Windows installer was supplied, follow the source steps below on a Windows 11 x64 PC. A macOS `.app` or `.dmg` cannot run on Windows and cannot be converted into a Windows executable by changing its filename.

## 2. Prerequisites for running and building source

Install the official [Python install manager](https://www.python.org/downloads/latest/pymanager/), using the [Python Windows instructions](https://docs.python.org/3/using/windows.html). Open a new PowerShell window after installation. Ask the manager for Python 3.12:

```powershell
py install 3.12
py -V:3.12 -c "import sys, struct; print(sys.version); print('Bits:', struct.calcsize('P') * 8); assert struct.calcsize('P') == 8"
```

The second command must report Python 3.12 and 64 bits. If you already have a conventional 64-bit Python 3.12 installer and the legacy Python launcher, `py -3.12` can be used in place of `py -V:3.12`; `py install` is specific to the newer install manager. Do not use an embedded Python ZIP, 32-bit Python, or a source-only Python archive for these steps.

Extract the GraphCad source folder into your Documents folder. The folder containing `run_graphcad.py`, `GraphCad.spec`, and `requirements.txt` is the project root. Open PowerShell there, or change to it:

```powershell
Set-Location "$env:USERPROFILE\Documents\GraphCad"
```

The pinned PySide6 wheels include the required Qt runtime. PyInstaller supplies a precompiled Windows bootloader. **Visual Studio, a C++ compiler, CMake, and a separately installed Qt SDK are not required for this wheel-based build.** A compiler is only needed if you deliberately change this process to build Python, Qt/PySide, native dependencies, or the PyInstaller bootloader from source. See [Qt's supported platforms](https://doc.qt.io/qt-6.10/supported-platforms.html) and [PyInstaller's bootloader documentation](https://pyinstaller.org/en/stable/bootloader-building.html).

## 3. Create an isolated environment and run

```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe run_graphcad.py
```

No environment activation is necessary. Using the explicit environment executable also avoids PowerShell execution-policy restrictions on activation scripts. `--only-binary=:all:` installs prebuilt wheels and stops if a suitable wheel is unavailable instead of silently compiling native code.

To open a project directly:

```powershell
.\.venv\Scripts\python.exe run_graphcad.py '.\examples\supply-demand.graphite'
```

Use an actual project path if your source package uses a different example filename. The legacy `run_graphite.py` entry remains available. The internal `graphite` Python package and `.graphite` document extension are intentionally preserved.

## 4. Test and build the desktop application

Install the development tools, run the tests, and build on the Windows PC:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build.py --work .\build-work --test
```

The final command uses `GraphCad.spec`. It writes the application to:

```text
dist\GraphCad\GraphCad.exe
dist\GraphCad\_internal\...
```

Keep **the whole `dist\GraphCad` folder together**. Copying only `GraphCad.exe` loses Python and Qt libraries. The chosen `--work .\build-work` keeps all compiler-analysis files, icons, cache, and collected dependency notices inside the project. Omit `--work` to use the default `..\..\work\graphcad-pyinstaller` directory. The application uses separate replaceable libraries rather than a self-extracting one-file package.

## 5. Validate the actual Windows build

Launch the executable from Explorer, or run:

```powershell
Start-Process '.\dist\GraphCad\GraphCad.exe'
```

For an automated frozen-build check with a reliable process exit code:

```powershell
$graphcadReport = Join-Path $env:TEMP 'graphcad-build-verification'
$graphcadProcess = Start-Process -FilePath '.\dist\GraphCad\GraphCad.exe' -ArgumentList @('--verify-build', ('"{0}"' -f $graphcadReport)) -Wait -PassThru
if ($graphcadProcess.ExitCode -ne 0) { throw "GraphCad verification failed: $($graphcadProcess.ExitCode)" }
Get-Content (Join-Path $graphcadReport 'verification.json')
```

The directory contains an editable document and PNG/PDF/SVG/DXF outputs, plus the verification report. The helper validates the installed build's dependencies and produced files. It does not test every human interaction or prove DWG compatibility. See `docs/TEST_RESULTS.md` for checks actually executed for this delivery.

Before distributing the Windows build, manually check it on the target PC at 1920×1080 with Windows scaling set to 100%, then 125%: resize the window, open every dock, edit axes, draw and drag points/lines/curves/arrows, edit a function, edit scatter data and its regression, save/reopen, and export. Confirm dialog buttons and the canvas remain reachable. Record the OS, scaling, and results; a test run on macOS does not establish these Windows results.

## 6. Create the installer

Install **Inno Setup 6**, available in the version-6 section of the [official downloads page](https://jrsoftware.org/isdl.php#v6). The supplied CI configuration pins version 6.7.4; current Inno Setup 7 is a different installation path. Review [Inno Setup's license](https://jrsoftware.org/files/is/license.txt), including its commercial-use information. Inno Setup is a build tool and is not embedded in GraphCad.

After the application folder has been built, run:

```powershell
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '.\packaging\windows.iss'
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed: $LASTEXITCODE" }
```

If Inno Setup was installed somewhere else, use its actual `ISCC.exe` path. The output is:

```text
dist\GraphCad-1.1.0-Windows-x64-Setup.exe
```

The installer defaults to `%LOCALAPPDATA%\Programs\GraphCad`, creates per-user shortcuts, and registers `.graphite` under Open With. It retains the previous Graphite installer AppId and `Graphite.Document` file association identity. An upgrade can therefore retain an existing Graphite installation directory; that is intentional compatibility behavior. The old `Graphite.exe` and its known shortcuts are replaced by GraphCad. User documents are not removed.

Test installation, launching, project association, upgrading an existing installation if applicable, and uninstalling on a separate Windows test account or VM before distribution. Those installer operations have not been executed here. Unsigned development binaries can trigger Windows reputation checks; a release distributor can sign the application and installer with their own certificate and [Windows SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool). A code-signing SDK is optional for release signing, not required to run or package the wheel-based application.

## Common problems

| Symptom | Resolution |
|---|---|
| `py` is not recognized | Install Python's official install manager, reopen PowerShell, and check Windows app execution aliases using the Python Windows guide. |
| `py install` is not understood | You may have the legacy launcher. Use the manager or an existing 64-bit Python 3.12 with `py -3.12`. |
| `No matching distribution found` | Confirm Python 3.12, 64 bits, and the expected package index. Upgrade pip in `.venv`. Do not remove the wheel-only flag just to start compiling unexpected dependencies. |
| `No module named PySide6` or `ezdxf` | Run installation and the app with the same `.venv\Scripts\python.exe`. |
| A native library reports missing `VCRUNTIME140` or `MSVCP140` | Repair the Python/application installation. If the DLL is still unavailable, install Microsoft's official [supported Visual C++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170), then retry. This runtime package is distinct from Visual Studio or a compiler SDK. |
| `Could not find the Qt platform plugin windows` | Keep the complete onedir folder, including `_internal\PySide6`. Build from a clean environment; remove unrelated global `QT_PLUGIN_PATH` overrides from that terminal before retrying. |
| The app immediately closes | Run source mode in PowerShell to see the exception; run packaged `--verify-build` and inspect `verification.json`. |
| `ISCC.exe` cannot be found | Install Inno Setup 6 and use the actual installed compiler path. Inno Setup 7 normally uses another folder. |
| `File not found` for `dist\GraphCad\*` during installer creation | Finish `scripts\build.py` successfully before compiling the installer. |
| An output is locked or access is denied | Close the running built app before rebuilding. Use a writable source/output folder; keep user documents separate from the application folder. |
| DWG export requests ODA | This is an optional external converter. PNG, PDF, SVG, DXF, and project saving work without it. Follow `docs/EXPORTS.md`. |

## Offline installation and build

On a connected Windows x64 machine with the same Python version, download wheels:

```powershell
py -V:3.12 -m pip download --only-binary=:all: -r requirements-dev.txt -d wheels
```

Copy the source and `wheels` folder to the offline Windows PC, create `.venv`, and install with:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheels -r requirements-dev.txt
```

Use the standalone installer or complete application folder for ordinary offline use; users of a packaged release do not need this build environment.
