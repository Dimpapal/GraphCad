"""Build a native, replaceable-library desktop bundle on the current platform."""
from __future__ import annotations
import argparse
import importlib.metadata
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]


def build_icon(work: Path) -> Path:
    """Rasterize the original vector icon for native Finder/Explorer metadata."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ROOT / 'packaging' / 'icon.svg'))
    def image(size: int) -> QImage:
        result = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return result
    work.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'darwin':
        folder = work / 'GraphCad.iconset'
        folder.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            image(size).save(str(folder / f'icon_{size}x{size}.png'))
            image(size * 2).save(str(folder / f'icon_{size}x{size}@2x.png'))
        icon = work / 'GraphCad.icns'
        # Modern ICNS containers accept PNG payloads directly. Writing the
        # documented chunk structure also works on headless build agents where
        # iconutil can fail to initialize image conversion services.
        chunks = []
        for tag, filename in ((b'icp4', 'icon_16x16.png'), (b'icp5', 'icon_32x32.png'),
                              (b'icp6', 'icon_32x32@2x.png'), (b'ic07', 'icon_128x128.png'),
                              (b'ic08', 'icon_256x256.png'), (b'ic09', 'icon_512x512.png'),
                              (b'ic10', 'icon_512x512@2x.png')):
            png = (folder / filename).read_bytes()
            chunks.append(tag + struct.pack('>I', len(png) + 8) + png)
        payload = b''.join(chunks)
        icon.write_bytes(b'icns' + struct.pack('>I', len(payload) + 8) + payload)
    else:
        icon = work / 'GraphCad.ico'
        if not image(256).save(str(icon), 'ICO'):
            raise RuntimeError('Qt could not generate the native application icon.')
    return icon


def collect_licenses(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    packages = ['PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6',
                'ezdxf', 'numpy', 'fonttools', 'pyparsing', 'typing_extensions',
                'altgraph', 'macholib', 'packaging', 'pyinstaller', 'pyinstaller-hooks-contrib']
    report = ['GraphCad runtime and bundler dependency notices', '',
              'Original application: MIT, see licenses/LICENSE.',
              'Qt/PySide6/Shiboken: LGPLv3 / GPL alternatives. See licenses/qt and LICENSES.md.',
              'Qt and PySide6 are unmodified dynamically loaded libraries.', '']
    for name in packages:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        folder = destination / name
        folder.mkdir(exist_ok=True)
        report.append(f'{name} {dist.version}: {dist.metadata.get("License-Expression", dist.metadata.get("License", "see package metadata"))}')
        (folder / 'METADATA.txt').write_text(dist.read_text('METADATA') or f'{name} {dist.version}', encoding='utf-8')
        for filename in dist.files or []:
            parts = filename.parts
            if '.dist-info' not in str(filename) or not any(part.lower().startswith(('license', 'copying', 'notice')) for part in parts):
                continue
            source = Path(dist.locate_file(filename))
            if source.is_file():
                target = folder / Path(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    for source in [Path(sys.base_prefix) / 'LICENSE.txt', Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt']:
        if source.is_file():
            shutil.copyfile(source, destination / 'PYTHON-LICENSE.txt')
            break
    (destination / 'NOTICE.txt').write_text('\n'.join(report) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    parser.add_argument('--work', type=Path, default=ROOT.parent.parent / 'work' / 'graphcad-pyinstaller')
    parser.add_argument('--test', action='store_true', help='Run the automated suite before packaging')
    args = parser.parse_args()
    if sys.platform not in ('win32', 'darwin'):
        parser.error('Release packaging is configured for Windows and macOS; build on the target OS.')
    if args.test:
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=ROOT, env=env, check=True)
    licenses = args.work.resolve() / 'licenses'
    collect_licenses(licenses)
    icon = build_icon(args.work.resolve() / 'icon')
    env = dict(os.environ, GRAPHCAD_LICENSE_DIR=str(licenses), GRAPHITE_LICENSE_DIR=str(licenses),
               GRAPHCAD_ICON=str(icon), GRAPHITE_ICON=str(icon), PYINSTALLER_CONFIG_DIR=str(args.work.resolve() / 'cache'))
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--workpath', str(args.work.resolve() / 'build'), '--distpath', str(args.dist.resolve()),
               str(ROOT / 'GraphCad.spec')]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    artifact = args.dist / ('GraphCad.app' if sys.platform == 'darwin' else 'GraphCad')
    print(f'Built {artifact.resolve()} for the current Python/OS architecture.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
