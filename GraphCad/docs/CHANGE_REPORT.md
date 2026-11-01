# GraphCad 1.1 implementation report

GraphCad extends the existing Graphite source. The earlier delivery remains preserved separately; the complete updated project is in `GraphCad/`. The UI, document model, renderer, history, math parser and packaging architecture were extended rather than replaced.

## Implemented requirements

| Request | Delivered implementation and verification |
| --- | --- |
| Point-to-line snapping | True document-coordinate projection, finite clamping/infinite extent, polyline edges, adjustable screen-pixel tolerance, target highlights, single-point creation/dragging; tested at unequal axis scales and multiple zooms |
| Automatic perpendicular | Linked foot and connector using existing object kinds, source/target/axis selection, updates on edits/load/export, cycle validation, zero connector, degeneracy/deletion policies, detach command, undo/redo tests |
| Dark mode | Light/Dark/System palette and global styling, toolbar plus View menu selector, persisted setting, theme-aware icons, source screenshots and export-pixel invariance tests |
| PNG defaults | API and dialog default1920×1080, custom dimensions and aspect lock, independent geometry rendering, no editor overlays |
| Orientation controls | Precision dialog, free/horizontal/vertical/reference parallel/perpendicular/angular/custom angle modes, creation and handle editing, apply to selected lines/arrows, visible active mode, explicit reset when a reference is lost |
| Pearson correlation | Direct centered-product calculation, signed r shown beside R²/equation in data statistics and fit status; insufficient/constant cases undefined; known datasets and updates tested |
| Rename | GraphCad1.1 branding, runtime/bundle metadata, launch command, spec, installer/DMG, icon and documentation; internal compatibility IDs retained intentionally |
| UI polish | Compact icon export button at toolbar edge, consistent themes/spacing/labels, advanced precision controls in a dialog, accessible action labels and tooltips |

## Compatibility decisions

The Python package `graphite`, compatibility launcher `run_graphite.py`, `.graphite` suffix, `graphite-document` identifier, macOS bundle ID, Windows installer AppId/ProgID, DXF XDATA identity, original MIT copyright and legacy environment-variable support are preserved. The primary launcher/build output is GraphCad. Existing recent-project/settings data is migrated once to the renamed settings store. New files can contain optional fields unknown to older Graphite readers; backward opening in Graphite1.0 is not promised.

User-visible error dialogs and help branding are updated. `docs/PROJECT_BRIEF.md` is retained as a historical original request rather than rewriting its historical product name.

## Validation and deliverables

- Source suite: **224 passed in3.29seconds**, no failures/skips. [Full results](TEST_RESULTS.md), [JUnit](test-results.xml).
- Native macOS application and README screenshots actually launched/captured. [Screenshots](images/graphcad-dark.png).
- Final Apple Silicon PyInstaller bundle: strict ad hoc signature verification passed; native Cocoa startup exited0.
- Frozen verification: all7checks passed. [Machine-readable evidence](frozen-verification.json).
- DMG: `dist/GraphCad-1.1.0-macOS-arm64.dmg`,54,093,765bytes; `hdiutil verify` passed, mounted app verified and executable compared with tested bundle, Applications shortcut present, then unmounted.
- Updated standalone source package: `GraphCad-1.1.0-source.zip` (top-level directory GraphCad).
- [Windows11x64 prerequisites, build, executable, installer and troubleshooting](WINDOWS11.md).
- [GitHub README](../README.md) includes all requested sections, real screenshots and repository-relative Releases/Issues links. No public repository URL or contact identity was supplied; no external repository was created or published.

## Limits and unverified work

Windows11x64 and Intel macOS binaries were not built/run here. Windows installer execution, upgrades, DPI behavior and release signing remain to be verified on Windows. The macOS image is a development build with an ad hoc signature, no Developer ID/notarization. Actual ODA DWG conversion and CAD-viewer compatibility remain unverified; PNG/PDF/SVG/DXF are implemented and exercised. System-theme detection is connected, but an actual live OS appearance change was not physically exercised. See the README and test report for mathematical sampling, snapping/group movement and other retained limits.

## File changes

No dependency library was added. File lists compare this complete source with the previous Graphite delivery, excluding runtime/build products and caches.

### Modified (35)

- `.github/workflows/build.yml`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/BUILD.md`
- `docs/EXPORTS.md`
- `docs/FORMAT.md`
- `docs/LICENSES.md`
- `docs/TEST_RESULTS.md`
- `docs/frozen-verification.json`
- `docs/test-results.xml`
- `examples/README.md`
- `examples/mathematics.graphite`
- `examples/mixed-workflow.dxf`
- `examples/mixed-workflow.graphite`
- `examples/mixed-workflow.pdf`
- `examples/mixed-workflow.svg`
- `examples/scatter-regression.graphite`
- `examples/supply-demand.graphite`
- `graphite/__init__.py`
- `graphite/app.py`
- `graphite/canvas.py`
- `graphite/data.py`
- `graphite/dialogs.py`
- `graphite/export.py`
- `graphite/geometry.py`
- `graphite/inspector.py`
- `graphite/model.py`
- `graphite/window.py`
- `packaging/icon.svg`
- `packaging/make_dmg.sh`
- `packaging/windows.iss`
- `pyproject.toml`
- `scripts/build.py`
- `scripts/create_examples.py`
- `tests/test_window.py`

### Added (20)

- `GraphCad.spec`
- `docs/CHANGE_REPORT.md`
- `docs/WINDOWS11.md`
- `docs/images/graphcad-dark.png`
- `docs/images/graphcad-light.png`
- `docs/images/graphcad-precision.png`
- `docs/images/graphcad-regression.png`
- `examples/perpendicular.graphite`
- `examples/perpendicular.png`
- `graphite/constructions.py`
- `graphite/themes.py`
- `packaging/windows_version.txt`
- `run_graphcad.py`
- `tests/fixtures/graphite-v1/mathematics.graphite`
- `tests/fixtures/graphite-v1/mixed-workflow.graphite`
- `tests/fixtures/graphite-v1/scatter-regression.graphite`
- `tests/fixtures/graphite-v1/supply-demand.graphite`
- `tests/test_graphcad_canvas.py`
- `tests/test_graphcad_geometry.py`
- `tests/test_graphcad_ui.py`

### Removed (2)

- `Graphite.spec`
- `docs/editor.png`

