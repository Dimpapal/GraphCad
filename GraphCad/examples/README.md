# Editable examples

Open any `.graphite` file with File → Open or pass its path to `run_graphcad.py`.

- `supply-demand.graphite`: independently editable lines, an equilibrium point, dashed guides, and axis labels.
- `mixed-workflow.graphite`: an expression-based demand function, a manually editable supply spline, a drag-style shift arrow, point and construction labels sharing one coordinate system.
- `mathematics.graphite`: four quadrants, quadratic and trigonometric functions, and a reciprocal with a discontinuity.
- `scatter-regression.graphite`: editable observations and a linked linear least-squares line. Double-click the dataset or fit in Objects to edit values and see statistics.

`mixed-workflow.png`, `.pdf`, `.svg` and `.dxf` are actual generated samples. The PDF/SVG contain vectors, and DXF contains editable CAD geometry. No DWG sample is supplied because no ODA converter is installed.

Regenerate these examples with `python scripts/create_examples.py` in an installed source environment.

- `perpendicular.graphite`: linked source point, foot, perpendicular connector and reference line; `perpendicular.png` is a Full HD export.
