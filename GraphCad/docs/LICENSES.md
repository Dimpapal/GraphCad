# Dependencies and redistribution

GraphCad continues the Graphite editor. Its original MIT `LICENSE` and the copyright notice for Graphite contributors are preserved unchanged; the product rename does not replace prior attribution. Third-party software keeps its own license. The project uses Qt Widgets, Gui, Core, Svg, and related runtime components; it does not use Qt WebEngine or browser technology.

| Dependency | Pinned version | Role | License |
|---|---|---|---|
| Python | 3.12 (tested 3.12.14) | Runtime | Python Software Foundation license |
| PySide6 / Qt | 6.10.2 | Native UI, vector rendering, PDF/SVG | LGPLv3 / GPL alternatives or commercial Qt license; module and third-party notices also apply |
| Shiboken6 | 6.10.2 (PySide dependency) | Bindings runtime | LGPLv3 / GPL alternatives |
| ezdxf | 1.4.5 | CAD DXF writing | MIT |
| NumPy | 2.5.4 | ezdxf dependency | BSD-3-Clause plus bundled notices |
| fonttools | 4.68.0 | ezdxf dependency | MIT plus embedded third-party notices |
| pyparsing | 3.3.3 | ezdxf dependency | MIT |
| typing_extensions | 4.16.0 | ezdxf dependency | PSF license |
| PyInstaller | 6.22.3 | Build-time freezer and runtime bootloader | GPL with exception allowing distribution of non-GPL applications |
| pytest | 9.2.0 | Development tests only | MIT |
| PyMuPDF | 2.0 | Optional PDF inspection in tests only | AGPLv3 or commercial; explicitly excluded from the application bundle |
| Inno Setup | 6.7.4 in CI | Optional Windows installer compiler | Separate Inno Setup terms; commercial users should review the vendor's licensing information |
| ODA File Converter | Optional user installation | DWG conversion | Separate ODA terms; neither downloaded nor bundled here |

The build collects installed distribution metadata and license files for runtime dependencies and the PyInstaller bootloader. Bundles include copies of GNU LGPLv3 and GPLv3 under `licenses/qt/`. Qt/PySide copyright belongs to The Qt Company Ltd. and other contributors. Qt is a trademark of The Qt Company Ltd.; this application is independent.

Qt/PySide remain dynamically loaded replaceable libraries in the PyInstaller onedir layout. The original Python application source, requirements, and rebuild configuration are delivered alongside the bundle. To modify or relink, replace the dependencies in a source environment and rebuild using `docs/BUILD.md`; avoid changing binary libraries in a signed app without re-signing or rebuilding it.

Before redistributing a release, retain the included notices and license texts, comply with applicable LGPL/GPL source and installation-information obligations for the exact libraries distributed, and provide the relevant corresponding library source or a compliant source offer. Merely linking to a website is not a universal substitute for those obligations. The supplied developer application is ad hoc signed by PyInstaller; it has no Developer ID signature or notarization. No commercial Qt or ODA license has been purchased or inferred.

Official sources and terms:

- [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
- [Qt LGPLv3 text and combined-work conditions](https://doc.qt.io/qt-6/lgpl.html).
- [Qt source archives](https://download.qt.io/archive/qt/6.10/6.10.2/) and [PySide source repository](https://code.qt.io/cgit/pyside/pyside-setup.git/), tag `v6.10.2`.
- [ezdxf source and MIT license](https://github.com/mozman/ezdxf).
- [PyInstaller license and bootloader exception](https://pyinstaller.org/en/stable/license.html).
- [Inno Setup license](https://jrsoftware.org/files/is/license.txt) and [commercial-use information](https://jrsoftware.org/isorder.php).
- [ODA converter distribution](https://www.opendesign.com/guestfiles/oda_file_converter).

License metadata is factual dependency information. This document does not grant rights over third-party software beyond its governing licenses.
