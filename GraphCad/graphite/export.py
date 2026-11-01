"""Clean raster, vector and CAD exports from the editable world-coordinate model.

Every format is written to a temporary sibling then atomically replaces the target.
DWG is an explicit optional conversion, never a renamed DXF file.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import math
import os
import shutil
import subprocess
import tempfile

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

from .data import linear_regression
from .expressions import sample_function
from .geometry import clip_line, format_number, smooth_curve, ticks
from .model import Document
from .render import Renderer


@dataclass
class ExportOptions:
    width: int = 1920
    height: int = 1080
    transparent: bool = False
    axes: bool = True
    grid: bool = True
    labels: bool = True
    margin: float = 60
    bounds: tuple[float, float, float, float] | None = None
    page_size: str = "A4"
    landscape: bool = True
    custom_width_mm: float = 297
    custom_height_mm: float = 210

    def validate(self) -> None:
        if (not isinstance(self.width, int) or not isinstance(self.height, int)
                or not 64 <= self.width <= 16000 or not 64 <= self.height <= 16000
                or self.width * self.height > 64_000_000):
            raise ValueError("Export dimensions must be 64–16000 pixels, at most 64 million pixels in total.")
        if not math.isfinite(self.margin) or not 0 <= self.margin < min(1000, 1000 * self.height / self.width) / 2 - 5:
            raise ValueError("Export margin must leave a positive drawing area.")
        if self.bounds is not None:
            if len(self.bounds) != 4 or not all(math.isfinite(v) for v in self.bounds):
                raise ValueError("Export bounds must contain four finite coordinates.")
            if self.bounds[0] >= self.bounds[1] or self.bounds[2] >= self.bounds[3]:
                raise ValueError("Export minimum coordinates must be less than maximum coordinates.")
        if self.page_size not in {"A4", "Letter", "Custom"}:
            raise ValueError("Page size must be A4, Letter or Custom.")
        if not all(math.isfinite(v) and 20 <= v <= 2000 for v in (self.custom_width_mm, self.custom_height_mm)):
            raise ValueError("Custom page dimensions must be 20–2000 mm.")


def _options(options: ExportOptions | None) -> ExportOptions:
    options = options or ExportOptions()
    options.validate()
    return options


def _bounds(doc: Document, options: ExportOptions) -> tuple[float, float, float, float]:
    return options.bounds or (doc.x_axis.minimum, doc.x_axis.maximum,
                              doc.y_axis.minimum, doc.y_axis.maximum)


def _atomic(path: str | Path, write: Callable[[Path], None]) -> None:
    target = Path(path).expanduser()
    if not target.parent.is_dir():
        raise OSError(f"Export directory does not exist: {target.parent}")
    handle, temporary = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=target.suffix, dir=target.parent)
    os.close(handle)
    temp = Path(temporary)
    try:
        write(temp)
        if not temp.is_file() or temp.stat().st_size == 0:
            raise OSError("The export engine did not produce a file.")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def _draw(painter: QPainter, doc: Document, options: ExportOptions) -> None:
    # Output resolution changes sharpness, not the relative weight of text,
    # markers or strokes. All exports share a 1000-unit logical design width.
    logical_width, logical_height = 1000.0, 1000.0 * options.height / options.width
    painter.save()
    painter.scale(options.width / logical_width, options.width / logical_width)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    rect = QRectF(options.margin, options.margin, logical_width - 2 * options.margin,
                  logical_height - 2 * options.margin)
    renderer = Renderer(doc, rect, bounds=_bounds(doc, options))
    try:
        renderer.draw(painter, selection=set(), handles=False, axes=options.axes,
                      grid=options.grid, labels=options.labels,
                      background=QColor(Qt.GlobalColor.transparent) if options.transparent else QColor("white"))
    finally:
        painter.restore()


def export_png(doc: Document, path: str | Path, options: ExportOptions | None = None) -> None:
    doc.update_constructions()
    options = _options(options)
    def write(target: Path) -> None:
        image = QImage(options.width, options.height, QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            raise OSError("Unable to allocate the requested image.")
        image.fill(Qt.GlobalColor.transparent if options.transparent else Qt.GlobalColor.white)
        image.setDotsPerMeterX(11811)
        image.setDotsPerMeterY(11811)
        painter = QPainter(image)
        try:
            _draw(painter, doc, options)
        finally:
            painter.end()
        if not image.save(str(target), "PNG"):
            raise OSError(f"Unable to save PNG: {path}")
    _atomic(path, write)


def export_pdf(doc: Document, path: str | Path, options: ExportOptions | None = None) -> None:
    doc.update_constructions()
    options = _options(options)
    def write(target: Path) -> None:
        writer = QPdfWriter(str(target))
        writer.setCreator("GraphCad")
        writer.setTitle(doc.title)
        writer.setResolution(72)
        page = (QPageSize(QPageSize.PageSizeId.A4) if options.page_size == "A4" else
                QPageSize(QPageSize.PageSizeId.Letter) if options.page_size == "Letter" else
                QPageSize(QSizeF(options.custom_width_mm, options.custom_height_mm), QPageSize.Unit.Millimeter))
        orientation = QPageLayout.Orientation.Landscape if options.landscape else QPageLayout.Orientation.Portrait
        writer.setPageLayout(QPageLayout(page, orientation, QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter))
        painter = QPainter()
        if not painter.begin(writer):
            raise OSError(f"Unable to open PDF output: {path}")
        try:
            if not options.transparent:
                painter.fillRect(QRectF(0, 0, writer.width(), writer.height()), QColor("white"))
            scale = min(writer.width() / options.width, writer.height() / options.height)
            painter.translate((writer.width() - options.width * scale) / 2,
                              (writer.height() - options.height * scale) / 2)
            painter.scale(scale, scale)
            _draw(painter, doc, options)
        finally:
            painter.end()
    _atomic(path, write)


def export_svg(doc: Document, path: str | Path, options: ExportOptions | None = None) -> None:
    doc.update_constructions()
    options = _options(options)
    def write(target: Path) -> None:
        generator = QSvgGenerator()
        generator.setFileName(str(target))
        generator.setSize(QSize(options.width, options.height))
        generator.setViewBox(QRectF(0, 0, options.width, options.height))
        generator.setTitle(doc.title)
        generator.setDescription("Editable vector graph exported by GraphCad")
        painter = QPainter()
        if not painter.begin(generator):
            raise OSError(f"Unable to open SVG output: {path}")
        try:
            if not options.transparent:
                painter.fillRect(QRectF(0, 0, options.width, options.height), QColor("white"))
            _draw(painter, doc, options)
        finally:
            painter.end()
    _atomic(path, write)


def export_dxf(doc: Document, path: str | Path, options: ExportOptions | None = None) -> None:
    """Export world geometry as AutoCAD 2010 DXF; manual splines are sampled polylines.

    Device-sized markers/labels/arrowheads use the chosen export dimensions to
    determine their world-coordinate size. Hidden entities are omitted.
    """
    import ezdxf
    from ezdxf import colors
    doc.update_constructions()
    options = _options(options)
    bounds = _bounds(doc, options)
    xmin, xmax, ymin, ymax = bounds
    logical_width, logical_height = 1000.0, 1000.0 * options.height / options.width
    renderer = Renderer(doc, QRectF(options.margin, options.margin, logical_width - 2 * options.margin,
                                   logical_height - 2 * options.margin), bounds=bounds)
    xunit = 1 / renderer.transform.sx
    yunit = 1 / renderer.transform.sy
    def write(target: Path) -> None:
        drawing = ezdxf.new("R2010")
        drawing.header["$INSUNITS"] = 0  # unitless mathematical coordinates
        drawing.header["$PDMODE"] = 35
        drawing.appids.new("GRAPHITE")
        for name, pattern in (("GRAPHITE_DASHED", [0.12, 0.08, -0.04]),
                              ("GRAPHITE_DOTTED", [0.04, 0, -0.04]),
                              ("GRAPHITE_DASHDOT", [0.18, 0.08, -0.04, 0, -0.06])):
            drawing.linetypes.new(name, dxfattribs={"description": name, "pattern": pattern})
        space = drawing.modelspace()
        def layer_name(name: str) -> str:
            clean = "".join(c if c not in '<>/\\":;?*|=,`' and ord(c) >= 32 else "_" for c in str(name))[:200] or "Drawing"
            if clean not in drawing.layers:
                drawing.layers.new(clean)
            return clean
        def attribs(style: dict, layer: str = "Drawing") -> dict:
            color = QColor(style.get("color", "#26384a"))
            if not color.isValid():
                color = QColor("#26384a")
            lineweight = min((5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211),
                             key=lambda v: abs(v - float(style.get("width", 2)) * 15))
            result = {"layer": layer_name(layer), "true_color": colors.rgb2int((color.red(), color.green(), color.blue())),
                      "lineweight": lineweight,
                      "linetype": {"dashed": "GRAPHITE_DASHED", "dotted": "GRAPHITE_DOTTED", "dash-dot": "GRAPHITE_DASHDOT",
                                   "dashdot": "GRAPHITE_DASHDOT"}.get(style.get("line_style"), "CONTINUOUS")}
            opacity = max(0, min(1, float(style.get("opacity", 1))))
            if opacity < 1:
                result["transparency"] = colors.float2transparency(1 - opacity)
            return result
        def line(a, b, attr):
            clipped = clip_line(a, b, bounds)
            return space.add_line(*clipped, dxfattribs=attr) if clipped else None
        def polyline(points, attr):
            # Clipping each segment prevents CAD extents being dominated by poles.
            run = []
            for a, b in zip(points, points[1:]):
                clipped = clip_line(a, b, bounds)
                if clipped is None:
                    if len(run) > 1:
                        space.add_lwpolyline(run, dxfattribs=attr)
                    run = []
                elif run and math.dist(run[-1], clipped[0]) < 1e-8:
                    run.append(clipped[1])
                else:
                    if len(run) > 1:
                        space.add_lwpolyline(run, dxfattribs=attr)
                    run = list(clipped)
            if len(run) > 1:
                space.add_lwpolyline(run, dxfattribs=attr)
        def text(content, at, style, layer="Labels"):
            if not content:
                return
            attr = attribs(style, layer)
            attr.pop("lineweight", None)
            attr.pop("linetype", None)
            attr.update({"height": float(style.get("font_size", 12)) * yunit,
                         "rotation": -float(style.get("rotation", 0)), "insert": tuple(at)})
            space.add_text(str(content), dxfattribs=attr)
        def triangle(start, end, size, attr):
            # Arrowhead is first constructed in device metric so anisotropic
            # coordinate ranges match the appearance of raster/vector exports.
            dx, dy = (end[0] - start[0]) / xunit, (end[1] - start[1]) / yunit
            length = math.hypot(dx, dy)
            if length <= 1e-10:
                return
            ux, uy = dx / length, dy / length
            size = min(float(size), length * .6)
            base = (end[0] - ux * size * xunit, end[1] - uy * size * yunit)
            left = (base[0] - uy * size * .45 * xunit, base[1] + ux * size * .45 * yunit)
            right = (base[0] + uy * size * .45 * xunit, base[1] - ux * size * .45 * yunit)
            space.add_solid([tuple(end), left, right, right], dxfattribs=attr)
        def marker(at, style, layer="Drawing"):
            if not xmin <= at[0] <= xmax or not ymin <= at[1] <= ymax:
                return
            attr = attribs(style, layer)
            entity = space.add_point(tuple(at), dxfattribs=attr)
            radius = float(style.get("marker_size", 6)) * xunit
            shape = style.get("marker", "circle")
            if shape in {"cross", "plus"}:
                for a, b in (((at[0] - radius, at[1]), (at[0] + radius, at[1])),
                             ((at[0], at[1] - radius * yunit / xunit), (at[0], at[1] + radius * yunit / xunit))):
                    line(a, b, attr)
            elif shape in {"square", "diamond"}:
                ry = radius * yunit / xunit
                points = ([(at[0] - radius, at[1] - ry), (at[0] + radius, at[1] - ry),
                           (at[0] + radius, at[1] + ry), (at[0] - radius, at[1] + ry)] if shape == "square" else
                          [(at[0], at[1] - ry), (at[0] + radius, at[1]), (at[0], at[1] + ry), (at[0] - radius, at[1])])
                space.add_lwpolyline(points, close=True, dxfattribs=attr)
            else:
                space.add_circle(tuple(at), radius, dxfattribs=attr)
            return entity

        # Grid remains independently controlled from axes and numeric labels.
        if options.grid:
            for minor, visible in ((True, doc.grid_minor), (False, doc.grid_major)):
                if not visible:
                    continue
                attr = attribs({"color": "#e9edf2" if minor else "#d9e1e9", "width": .5}, "Minor Grid" if minor else "Major Grid")
                for axis, low, high, vertical in ((doc.x_axis, xmin, xmax, True), (doc.y_axis, ymin, ymax, False)):
                    interval = axis.minor if minor else axis.major
                    if minor and interval <= 0:
                        continue
                    for value in ticks(low, high, interval):
                        line((value, ymin) if vertical else (xmin, value), (value, ymax) if vertical else (xmax, value), attr)
        if options.axes:
            for axis, horizontal in ((doc.x_axis, True), (doc.y_axis, False)):
                if not axis.visible:
                    continue
                low, high = (xmin, xmax) if horizontal else (ymin, ymax)
                cross = doc.y_axis.position if horizontal else doc.x_axis.position
                if not axis.negative:
                    low = max(cross, low)
                if not axis.positive:
                    high = min(cross, high)
                pos = axis.position
                if low > high or not (ymin <= pos <= ymax if horizontal else xmin <= pos <= xmax):
                    continue
                a, b = ((low, pos), (high, pos)) if horizontal else ((pos, low), (pos, high))
                style = {"color": "#26384a", "width": axis.width, "line_style": axis.line_style, "font_size": 12}
                attr = attribs(style, "Axes")
                line(a, b, attr)
                if axis.arrowheads in {"positive", "both"}:
                    triangle(a, b, 10, attr)
                if axis.arrowheads in {"negative", "both"}:
                    triangle(b, a, 10, attr)
                for value in ticks(low, high, axis.major):
                    at = (value, pos) if horizontal else (pos, value)
                    if axis.ticks:
                        line((at[0], at[1] - 3 * yunit) if horizontal else (at[0] - 3 * xunit, at[1]),
                             (at[0], at[1] + 3 * yunit) if horizontal else (at[0] + 3 * xunit, at[1]), attr)
                    if options.labels and axis.numbers and abs(value) > 1e-12:
                        text(format_number(value, axis.number_format, axis.decimals),
                             (at[0] - 3 * xunit, at[1] - 19 * yunit) if horizontal else (at[0] - 25 * xunit, at[1] - 4 * yunit), style)
                if options.labels and axis.title_visible:
                    text(axis.title, (high - 55 * xunit, pos - 38 * yunit) if horizontal else (pos + 12 * xunit, high - 12 * yunit), style)
            ox, oy = doc.y_axis.position, doc.x_axis.position
            if doc.origin_visible:
                marker((ox, oy), {"color": "#26384a", "marker_size": 4}, "Axes")
            if options.labels and doc.origin_label:
                text("0", (ox - 13 * xunit, oy - 18 * yunit), {"font_size": 12})

        for obj in doc.objects:
            if not obj.visible or not doc.type_visibility.get(obj.kind, True):
                continue
            style = obj.style
            attr = attribs(style, obj.layer)
            points = obj.points
            before = set(e.dxf.handle for e in space)
            if obj.kind == "point" and points:
                marker(points[0], style, obj.layer)
            elif obj.kind == "scatter":
                for index, p in enumerate(obj.data.get("rows", [])):
                    marker(p, style, obj.layer)
                    if options.labels and obj.data.get("point_labels"):
                        text(str(index + 1), (p[0] + 6 * xunit, p[1] + 6 * yunit), style)
            elif obj.kind == "text" and points:
                text(obj.data.get("text", obj.label), points[0], style, obj.layer)
            elif obj.kind in {"function", "regression", "curve"}:
                for segment in renderer.object_segments(obj):
                    polyline(segment, attr)
            elif obj.kind == "polyline":
                polyline(points, attr)
            elif len(points) >= 2:
                a, b = points[0], points[1]
                if obj.kind in {"infinite_line", "horizontal", "vertical"}:
                    for segment in renderer.object_segments(obj):
                        if len(segment) > 1:
                            line(segment[0], segment[-1], attr)
                else:
                    line(a, b, attr)
                if obj.kind == "arrow":
                    if style.get("arrow_end", True):
                        triangle(a, b, style.get("arrow_size", 12), attr)
                    if style.get("arrow_start", False):
                        triangle(b, a, style.get("arrow_size", 12), attr)
            label = obj.label
            if obj.kind == "point" and points:
                mode = obj.data.get("label_mode", "name")
                coords = f"({points[0][0]:g}, {points[0][1]:g})"
                label = coords if mode == "coordinates" else f"{label} {coords}".strip() if mode == "both" else label
            if options.labels and doc.labels_visible and label and obj.kind != "text" and obj.data.get("label_visible", True):
                p = obj.data.get("label_position") or (points[-1] if points else None)
                if p is None:
                    segments = renderer.object_segments(obj)
                    valid = [p for segment in segments for p in segment if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
                    p = valid[int(len(valid) * .85)] if valid else None
                if p is not None:
                    text(label, (p[0] + 8 * xunit, p[1] + 9 * yunit), style)
            for entity in space:
                if entity.dxf.handle not in before:
                    entity.set_xdata("GRAPHITE", [(1000, str(obj.id)), (1000, str(obj.name)[:250]), (1000, str(obj.label)[:250])])
        drawing.set_modelspace_vport(height=(ymax - ymin) * 1.25, center=((xmin + xmax) / 2, (ymin + ymax) / 2))
        drawing.saveas(target)
    _atomic(path, write)


def find_oda_converter(explicit: str | Path | None = None) -> str | None:
    candidates = [explicit, os.environ.get("GRAPHCAD_ODA_CONVERTER"), os.environ.get("GRAPHITE_ODA_CONVERTER"), shutil.which("ODAFileConverter"),
                  "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().is_file() and os.access(Path(candidate).expanduser(), os.X_OK):
            return str(Path(candidate).expanduser())
    return None


def export_dwg(doc: Document, path: str | Path, options: ExportOptions | None = None,
               converter: str | Path | None = None) -> None:
    """Run a separately installed, licensed ODA File Converter in isolated folders.

    CLI contract: input directory, output directory, version, type, recursive,
    audit, input filter. No shell is used. A successful exit and DWG signature
    are required, but compatibility still needs validation in the target CAD app.
    """
    doc.update_constructions()
    options = _options(options)
    executable = find_oda_converter(converter)
    if not executable:
        raise RuntimeError("DWG export requires a separately installed ODA File Converter. "
                           "Set GRAPHITE_ODA_CONVERTER to its executable, or export DXF.")
    with tempfile.TemporaryDirectory(prefix="graphite-dwg-") as temporary:
        source = Path(temporary) / "input"
        output = Path(temporary) / "output"
        source.mkdir()
        output.mkdir()
        export_dxf(doc, source / "drawing.dxf", options)
        command = [executable, str(source), str(output), "ACAD2018", "DWG", "0", "1", "*.dxf"]
        env = dict(os.environ)
        # PySide's plugin directory must not be injected into the converter's
        # independent Qt runtime.
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            env.pop(key, None)
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                                    env=env, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ODA File Converter did not finish within 120 seconds.") from exc
        converted = output / "drawing.dwg"
        if result.returncode or not converted.is_file():
            detail = (result.stderr or result.stdout).strip()[-1200:]
            raise RuntimeError(f"ODA conversion failed (exit {result.returncode}). {detail}")
        with converted.open("rb") as stream:
            signature = stream.read(6)
        if signature not in {b"AC1018", b"AC1021", b"AC1024", b"AC1027", b"AC1032"}:
            raise RuntimeError("Converter output is not a recognized binary DWG file.")
        _atomic(path, lambda target: shutil.copyfile(converted, target))
