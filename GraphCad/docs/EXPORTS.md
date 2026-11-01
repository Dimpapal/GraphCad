# Export formats

Save `.graphite` to preserve editable objects, expressions, datasets, styles, and graph settings. Exporting produces a separate presentation or CAD file; it does not replace saving the project.

| Format | Implementation | Preservation | Verification |
|---|---|---|---|
| PNG | Qt QImage, antialiased at requested pixel dimensions | Appearance; solid or transparent background | Dimensions, alpha channel, nonempty content, white background tested |
| PDF | Native QPdfWriter/QPainter | Vector paths, cubic curves, text, arrows, line styles | A4/Letter/custom page dimensions, rendered content, vector drawing commands, no embedded graph bitmap tested |
| SVG | Native QSvgGenerator/QPainter | Vector paths and text | XML parsed; vector paths and text present, no image element tested |
| DXF | ezdxf, AutoCAD 2010 format | World coordinate LINE, LWPOLYLINE, POINT/CIRCLE, TEXT and arrowhead SOLID entities; separate layers; object identity in GRAPHITE XDATA | Reopened with ezdxf, audit without errors, coordinates/entity types/layers/hidden geometry tested |
| DWG | Optional external ODA File Converter using the generated DXF | Binary CAD geometry via converter | Missing-dependency handling tested. Actual DWG generation and opening in a CAD application were **not tested** because ODA is not installed |

The automated file tests are in `tests/test_export.py`. A test passing in one environment does not establish compatibility with every viewer or CAD product.

## Export controls

PNG export defaults to **1920 × 1080 (Full HD)** in both the API and export dialog. The dialog's aspect-ratio lock starts enabled; changing one dimension adjusts the other. Turn it off for independent dimensions. PNG/SVG dimensions are 64–16000 pixels per side, limited to 64 million pixels total to bound allocation. Margins must leave a positive drawing area. PDF supports A4, US Letter, or custom dimensions from 20–2000 mm, portrait or landscape. The graph fits the page while retaining its chosen width-to-height ratio.

The UI can export the configured graph range, current view, or a custom numerical region. The API accepts explicit `(xmin,xmax,ymin,ymax)` bounds for a region. Axis, grid, and label options are independent. Hidden objects and hidden object types are omitted. Locked objects are included. Editor selections, control handles, tool previews, and interface panels are excluded. A transparent PDF omits the background fill; PDF viewers normally display the page as white. Rendering uses a stable 1000-unit logical width: doubling PNG resolution preserves the relative size of text, strokes, and markers. Margins are measured in these logical units. Axis fonts use logical pixel sizes, and a test confirms that image DPI metadata does not alter rendered layout.

Object geometry is clipped to the plotting range. Text labels can occupy the reserved axis/label margins. Margins reserve both the requested outer padding and the renderer's space for axis titles and tick labels. Exports write a temporary sibling file and atomically replace the destination only after successful generation.

The Light, Dark, and System themes change the editor interface. They do not change object colors, white plotting paper, or exported colors. Transparent output remains controlled by its export option. Snapping indicators, reference highlights, orientation guides, and selection/endpoint handles are editor overlays and are not included.

## Linked constructions and snapshots

Perpendicular constructions are resolved from their source point and target object/axis before export. The saved `.graphite` project retains `data.perpendicular` dependency metadata, allowing future edits to update the foot and connector. PNG/PDF/SVG and DXF export the resulting current geometry. A CAD export contains editable geometric entities, without the native application's dependency solver; it is a snapshot of the construction.

A finite segment is treated as its supporting infinite line for perpendicular construction, so its foot can lie beyond an endpoint. Point-to-segment snapping uses the finite segment and clamps to endpoints. If a construction dependency is deleted, its last coordinates are preserved, the link is removed, and its helper objects unlock. A directionless target retains the last valid construction rather than producing undefined geometry. Dependency cycles and malformed construction metadata are rejected.

## DXF geometry and approximations

One graph unit equals one unitless CAD drawing unit. No screen-coordinate conversion is applied to object positions. Infinite lines are clipped to the selected world range. Dashed construction lines retain line types. Functions, linked regressions, polylines, and editable Catmull–Rom curves are exported as sampled CAD polylines; the `.graphite` project retains their original formula or editable knots. PDF and SVG manual curves use cubic vector paths.

Point markers, label offsets, font sizes, and arrowheads have a device-sized appearance in GraphCad. DXF converts these sizes to world units using the same logical viewport as the visual exports, so resolution changes preserve their relative appearance. CAD applications may substitute fonts, vary line-type display scales, and render text/marker fills differently. Text, axes, and gridlines remain editable entities, not one raster image. Unicode text depends on the receiving application's font support. Rich text layout and exact font metrics are not CAD interchange guarantees.

## Optional DWG setup

1. Download and install [ODA File Converter from Open Design Alliance](https://www.opendesign.com/guestfiles/oda_file_converter). Review its own license. It is a separate optional dependency and is **not redistributed** with this project.
2. Set `GRAPHCAD_ODA_CONVERTER` to the actual executable path, then start GraphCad. The legacy `GRAPHITE_ODA_CONVERTER` remains a fallback. On macOS the standard `/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter` path is also detected. Windows users should use the installed `.exe` path.
3. Choose DWG export. GraphCad exports to an isolated temporary DXF directory and invokes:

   ```text
   ODAFileConverter INPUT_DIRECTORY OUTPUT_DIRECTORY ACAD2018 DWG 0 1 *.dxf
   ```

4. Open the resulting DWG in your intended CAD application before relying on it. GraphCad requires both a successful converter exit and a recognized binary DWG header, but these checks alone cannot prove full CAD compatibility.

ODA documents a GUI and command-line interface, with Windows 10+ x64 and macOS 13+ downloads for both Intel and Apple Silicon. That converter baseline is independent of GraphCad's own baseline. Its public download page does not establish redistribution rights; this project neither bundles it nor assumes those rights. A product that embeds a DWG SDK should arrange the appropriate [ODA SDK license](https://www.opendesign.com/). There is no direct native DWG writer in GraphCad and no renamed DXF fallback.

The ODA integration has a 120-second timeout. Conversion runs without a shell, in isolated input/output folders, and removes inherited Qt plugin search paths so the converter can use its own Qt runtime. A failure leaves an existing destination file unchanged.

Official rendering references: [QPdfWriter](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPdfWriter.html), [Qt painting devices](https://doc.qt.io/qt-6/painting.html).
