# Editable document format

`.graphite` is UTF-8 JSON with `format: "graphite-document"` and `version: 1`. `.graphproj` is accepted when opening; new saves use `.graphite`. A higher or unknown version is rejected with a useful message. Files above 64 MiB and malformed/non-finite/oversized geometry are rejected before editing.

A document stores its title, X and Y `Axis` records, ordered `objects`, major/minor grid visibility, origin marker/label, object-label and per-kind visibility, snapping preferences, coordinate mode, and trigonometric angle mode. The saved axis ranges define full-document exports. Temporary pan/zoom and selection are view state and do not mutate those ranges.

Each axis has `minimum`, `maximum`, `major`, `minor`, `title`, `visible`, `positive`, `negative`, `ticks`, `numbers`, `title_visible`, `arrowheads`, `position`, `label_side`, `number_format`, `decimals`, `width` and `line_style`. `position` is the mathematical value on the opposite axis at which this axis is drawn. Major interval zero means automatic, minor zero means off. Arrowheads are `none`, `positive`, `negative`, or `both`.

Each object stores a stable UUID `id`, `kind`, mathematical `points` (`[[x,y],...]`), independent `name`/`label`, `visible`, `locked`, group UUID, layer tag, `style` and `data`. Draw order is array order. Supported kinds are point, line/segment, infinite_line, horizontal, vertical, polyline, curve, arrow, text, function, scatter, regression, construction.

Style stores color, width, line_style, opacity, marker, marker_size, fill, font, font_size, bold, italic, align, rotation, arrow_start, arrow_end, arrow_size, background. Widths, marker radii, arrowheads and font sizes are logical display pixels, while point geometry uses double-precision mathematical coordinates.

Data fields include:

| Kind | Data |
| --- | --- |
| text | `text` (Unicode, newlines allowed) |
| function | `expression`, optional `domain_min`/`domain_max`, `offset_x`/`offset_y` |
| scatter | `rows`: editable X/Y pairs, `point_labels` |
| regression | `source_id` referencing a scatter object; coefficients recomputed from data |
| point | `label_mode`: name, coordinates, or both |
| all annotations | optional `label_position`: graph X/Y, `label_visible` |

Curve `points` are interpolating knots. Catmull–Rom tangents generate the cubic Bézier segments at render time. Functions retain expressions, not sampled paths. Regressions remain linked by source UUID, so editing a dataset recomputes geometry.

Saving validates the model, writes a temporary sibling file, flushes it to storage, and atomically replaces the destination. Undo/redo stores bounded before/after document snapshots for entire transactions, including axes, datasets, visibility and styles. This format is documented by `graphite/model.py`; unknown top-level/axis/object schema fields are rejected in version 1. Future schema changes should increment/migrate the version explicitly.


## GraphCad 1.1 additions

Legacy Graphite version-1 files load without migration. The application retains the `graphite-document` identifier, `.graphite` suffix, Python package and platform association IDs. New document fields `snap_lines` (default false) and `snap_tolerance_pixels` (default 10, range 1–50) are optional on loading. Earlier Graphite readers reject unknown fields, so opening a newly saved GraphCad document in Graphite 1.0 is not promised.

Linked perpendicular helpers are ordinary `point` and `construction` objects. Each uses `data.perpendicular = {role, source_id, target_id}` or `{role, source_id, axis}` with role `foot`/`segment` and axis `x`/`y`. A group UUID associates the two helpers. Materialized points remain present for vector export; validated references recompute them after editing, loading, saving and export. A bounded topological pass rejects dependency cycles. Helpers are locked while linked; styling, labels, naming and visibility remain editable. Detaching removes metadata and unlocks geometry. A missing reference freezes and detaches the helper; a temporarily degenerate target retains the last valid result until it recovers.

Drawing orientation is view/tool state. It does not retroactively constrain saved manual geometry or introduce a persistent relationship between ordinary lines. Theme preference is stored in application settings, not the document. Pearson statistics are calculated from dataset values rather than persisted as potentially stale coefficients.
