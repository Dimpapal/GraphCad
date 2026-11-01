# Build with: python scripts/build.py
from pathlib import Path
import os
import sys

root = Path(SPECPATH)
def setting(name, default=None):
    return os.environ.get('GRAPHCAD_' + name) or os.environ.get('GRAPHITE_' + name) or default

license_dir = Path(setting('LICENSE_DIR', root / 'packaging' / 'licenses'))
datas = [(str(root / 'LICENSE'), 'licenses'),
         (str(root / 'docs' / 'LICENSES.md'), 'licenses'),
         (str(root / 'docs' / 'BUILD.md'), 'docs'),
         (str(root / 'docs' / 'WINDOWS11.md'), 'docs'),
         (str(root / 'packaging' / 'licenses'), 'licenses/qt')]
if license_dir.is_dir():
    datas.append((str(license_dir), 'licenses/dependencies'))

a = Analysis([str(root / 'run_graphcad.py')], pathex=[str(root)], binaries=[],
             datas=datas, hiddenimports=['PySide6.QtSvg'],
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['tkinter', 'matplotlib', 'IPython', 'pandas', 'scipy', 'sympy',
                       'onnxruntime', 'pymupdf', 'fitz', 'pytest', 'networkx', 'psutil', 'PyQt5', 'PyQt6',
                       'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.Qt3DCore'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GraphCad', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, argv_emulation=False,
          icon=setting('ICON'),
          version=str(root / 'packaging' / 'windows_version.txt') if sys.platform == 'win32' else None,
          target_arch=None, codesign_identity=setting('CODESIGN_IDENTITY'),
          entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GraphCad')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='GraphCad.app', icon=setting('ICON'), bundle_identifier='io.graphite.editor',
                 info_plist={'CFBundleName': 'GraphCad',
                             'CFBundleShortVersionString': '1.1.0',
                             'CFBundleVersion': '1.1.0',
                             'NSHighResolutionCapable': True,
                             'LSMinimumSystemVersion': '14.0',
                             'CFBundleDocumentTypes': [{'CFBundleTypeName': 'GraphCad Diagram',
                                                       'CFBundleTypeExtensions': ['graphite'],
                                                       'CFBundleTypeRole': 'Editor'}]})
