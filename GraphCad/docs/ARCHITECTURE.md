# Architecture

GraphCad is an offline native Qt Widgets application. Python 3.12 hosts PySide6 bindings to Qt 6.10. There is no browser, JavaScript runtime, remote backend, or image-based drawing engine in ordinary editing. Qt's QPainter renders the same vector geometry to the native window, PNG, PDF, and SVG.

## Product rename and compatibility

GraphCad 1.1.0 continues the Graphite codebase. Public launchers and native bundles use `run_graphcad.py`, `graphcad`, `GraphCad.exe`, and `GraphCad.app`. The Python namespace `graphite`, legacy `run_graphite.py` launcher, `.graphite` extension, JSON format identifier/version, macOS bundle ID `io.graphite.editor`, Windows installer AppId, `Graphite.Document` ProgID, and DXF `GRAPHITE` XDATA remain stable. This keeps editable files and installation/document associations compatible while changing the product name. The source MIT license and prior contributors' attribution remain intact.

## Responsibilities

| Component | Responsibility |
|---|---|
| `app.py` | Native application lifecycle, identity, startup arguments |
| `window.py` | Menus, toolbars, dock panels, selection synchronization, document actions |
| `dialogs.py` | Validated axis, object, function, dataset, and export settings |
| `canvas.py` | Native pointer/keyboard gestures, preview tools, hit detection, handles, snapping, panning/zoom |
| `render.py` | Shared vector presentation, plot frame, axes/grid, markers, labels, object paths |
| `model.py` | Qt-independent dataclasses, validation, versioned JSON, atomic project persistence |
| `geometry.py` | Forward/inverse coordinate transforms, clipping, intersections, curve interpolation, intervals |
| `constructions.py` | Validated linked perpendicular dependencies, resolution order, foot/connector updates and detachment |
| `history.py` | Whole-document transactional undo/redo and saved-state tracking |
| `expressions.py` | Restricted arithmetic AST interpreter and adaptive function sampling |
| `data.py` | CSV validation, centered least-squares regression and signed Pearson correlation |
| `themes.py` | Interface-only Light/Dark/System palettes and style selection |
| `templates.py` | Fully editable mathematical and economics starting documents |
| `export.py` | Validated clean exports and optional external DWG conversion |

## Coordinate ownership

Object points, knots, dataset rows, domains, and axis limits are double-precision mathematical coordinates. ViewTransform owns only the current mathematical bounds and output rectangle. It applies an independent horizontal and vertical scale and reverses screen Y. Zooming and panning change view bounds; they never rewrite object coordinates. Saving stores the model, not screenshots or viewport-derived points.

Manual curves are interpolating Catmull–Rom splines through editable knots. Qt renders them as cubic Bézier path segments. Mathematical functions retain their expression and domain, and regenerate sampled geometry for the visible range. Undefined values and detected discontinuities split paths. Sampling is bounded; pathological oscillations cannot be perfectly resolved at every scale. Translated functions retain an offset rather than becoming anonymous point paths. Scatter objects retain editable rows, and regression objects refer to the dataset ID so coefficients update after edits.

Point-to-line snapping computes projection in mathematical coordinates and compares the candidate distance using a screen-pixel tolerance. Finite target segments clamp the snapped point to their endpoints. Fixed horizontal/vertical, reference parallel/perpendicular, incremental-angle and custom-angle constraints determine direction in world coordinates rather than in the potentially anisotropic screen projection.

Linked perpendicular helpers are ordinary point/construction objects carrying validated `data.perpendicular` source/target metadata. Their geometry is materialized for rendering, persistence and export. A bounded iterative topological pass resolves dependencies and rejects cycles before applying updates. Helpers start locked against direct geometry edits; names, labels, styles and visibility remain editable. A deleted dependency freezes and detaches the last materialized geometry, while a degenerate target retains its last valid result. Explicit detachment converts helpers to freely editable objects.

Pearson `r` uses centered sums and preserves its sign, independently from the least-squares `R²` statistic. Fewer than two pairs, or a constant X or Y variable, yields undefined correlation (`None`, displayed as `undefined`). A constant Y response retains the regression module's existing finite `R²=1` convention. The interface formats correlation with up to eight significant digits.

Interface themes use explicit application palettes. The document renderer uses document colors and white plotting paper independently of the palette, so theme changes do not recolor exports. Export dimensions default to 1920×1080 and a stable logical design width preserves relative text/marker/stroke sizes across output resolutions.

## Transactions

Creating, deleting, dragging, editing handles, and applying settings are document transactions. The canvas emits the pre-edit snapshot after completing a gesture. MainWindow commits it with a human-readable label. Undo/redo restores a validated complete document, including axis settings, object data, visibility, and style. Selection and viewport navigation are UI state and do not rewrite the document.

Snapshots favor reliability and straightforward extension over memory efficiency. A future version with very large documents could use structural sharing or targeted commands. The model bounds object counts, points, file sizes, numeric ranges, and nesting to reject malformed input and prevent accidental unbounded loads.

## File format

`.graphite` is UTF-8 JSON with a format identifier and version number. It contains `title`, independent `x_axis`/`y_axis` settings, all `objects`, and document display/snapping configuration. Every object has a stable ID, kind, separate internal name and displayed label, point geometry, visibility/lock/group/layer fields, style, and kind-specific `data`.

Functions use `data.expression`, `domain_min`, `domain_max`, and optional offsets. Scatter uses `data.rows`; regression uses `data.source_id`. Names and labels are independently editable. Layers and grouping are preserved model properties, while drawing order follows the ordered object list. Unknown future versions are rejected instead of being silently misinterpreted. Writes use temporary files in the destination directory before atomic replacement.

## Expression execution boundary

The function parser normalizes conventional notation (`2x`, `^`, `π`), parses it into an AST, validates every node, and interprets only arithmetic operators, `x`, known constants, and explicit one-argument math functions. It does not use `eval`, imports, Python attributes, subscripting, or arbitrary calls. Expression length, AST depth, and numeric exponents are bounded. Radians are the default; document settings can select degrees.

## Extension points

Add a new object kind in model validation, renderer geometry, property editing, and CAD export. Reuse world coordinates and commit a single transaction for each user action. Preserve separate native model and export semantics. Add nonlinear models beside centered least squares in `data.py`; add actual CAD SDKs behind the explicit optional DWG boundary rather than changing the document engine.
