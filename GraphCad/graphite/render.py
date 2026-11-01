"""Shared, device-independent Qt vector renderer used by the editor and exports."""
from __future__ import annotations

from functools import lru_cache
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF

from .geometry import ViewTransform, clip_line, smooth_curve, ticks, nice_interval
from .expressions import sample_function
from .data import linear_regression

LINE_STYLES = {'solid': Qt.PenStyle.SolidLine, 'dashed': Qt.PenStyle.DashLine,
               'dotted': Qt.PenStyle.DotLine, 'dash-dot': Qt.PenStyle.DashDotLine,
               'dashdot': Qt.PenStyle.DashDotLine}


def pen(color, width=1.0, style='solid'):
    p = QPen(QColor(color), float(width), LINE_STYLES.get(style, Qt.PenStyle.SolidLine))
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def axis_font(size=12):
    # Pixel sizes keep annotation layout independent of the paint device DPI.
    # Point sizes expand on a 300-DPI PNG and would differ from the PDF/canvas.
    font = QFont('Arial')
    font.setPixelSize(size)
    return font


def arrow_head(start, end, size):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return QPolygonF()
    ux, uy = dx / length, dy / length
    # A conventional filled triangular head, independent of viewport scaling.
    size = min(float(size), length * 0.65)
    return QPolygonF([QPointF(*end), QPointF(end[0] - size * ux - .43 * size * uy,
                                             end[1] - size * uy + .43 * size * ux),
                     QPointF(end[0] - size * ux + .43 * size * uy,
                             end[1] - size * uy - .43 * size * ux)])


@lru_cache(maxsize=256)
def _sample(expression, bounds, width, domain, radians):
    return sample_function(expression, *bounds, pixel_width=width, domain=domain, radians=radians)


class Renderer:
    """All positions are transformed from graph coordinates at render time.

    Pen widths, point markers, font sizes, and arrowheads are specified in logical
    output pixels, so zooming does not blur or inflate editor furniture.
    """
    def __init__(self, document, rect: QRectF, bounds=None):
        self.document = document
        self.rect = QRectF(rect)
        self.bounds = tuple(bounds or (document.x_axis.minimum, document.x_axis.maximum,
                                       document.y_axis.minimum, document.y_axis.maximum))
        self.plot = self.rect.adjusted(64, 36, -38, -66)
        if self.plot.width() < 20 or self.plot.height() < 20:
            self.plot = self.rect.adjusted(8, 8, -8, -8)
        self.transform = ViewTransform(self.bounds,
                                      (self.plot.x(), self.plot.y(), self.plot.width(), self.plot.height()))

    def visible(self, obj):
        return obj.visible and self.document.type_visibility.get(obj.kind, True)

    def _point(self, p):
        return QPointF(*self.transform.forward(p))

    def _path_from(self, points):
        result = QPainterPath()
        if points:
            result.moveTo(self._point(points[0]))
            for p in points[1:]:
                result.lineTo(self._point(p))
        return result

    def object_segments(self, obj):
        points = obj.points
        kind = obj.kind
        if kind == 'function':
            ox, oy = float(obj.data.get('offset_x', 0)), float(obj.data.get('offset_y', 0))
            xmin, xmax, ymin, ymax = self.bounds
            domain = (obj.data.get('domain_min'), obj.data.get('domain_max'))
            try:
                segments = _sample(obj.data.get('expression', 'x'),
                                   (xmin - ox, xmax - ox, ymin - oy, ymax - oy),
                                   max(100, min(4000, int(self.plot.width()))), domain,
                                   self.document.radians)
                return [[(x + ox, y + oy) for x, y in segment] for segment in segments]
            except (ValueError, TypeError, OverflowError):
                return []
        if kind == 'regression':
            source = next((o for o in self.document.objects if o.id == obj.data.get('source_id')), None)
            if source is None:
                return []
            try:
                fit = linear_regression(source.data.get('rows', []))
                xmin, xmax, _, _ = self.bounds
                return [[(xmin, fit.slope * xmin + fit.intercept),
                         (xmax, fit.slope * xmax + fit.intercept)]]
            except (ValueError, TypeError, OverflowError):
                return []
        if kind == 'scatter':
            return [obj.data.get('rows', [])]
        if kind == 'curve':
            return [smooth_curve(points)] if len(points) > 1 else [points]
        if kind in ('infinite_line', 'horizontal', 'vertical') and len(points) >= 2:
            a, b = list(points[0]), list(points[1])
            if kind == 'horizontal':
                b[1] = a[1]
            if kind == 'vertical':
                b[0] = a[0]
            clipped = clip_line(a, b, self.bounds, infinite=kind == 'infinite_line')
            return [list(clipped)] if clipped else []
        return [points]

    def object_path(self, obj):
        path = QPainterPath()
        size = max(1, float(obj.style.get('marker_size', 6)))
        if obj.kind == 'point' and obj.points:
            p = self._point(obj.points[0])
            path.addEllipse(p, size, size)
        elif obj.kind == 'scatter':
            for point in obj.data.get('rows', []):
                path.addEllipse(self._point(point), size, size)
        elif obj.kind == 'text' and obj.points:
            p = self._point(obj.points[0])
            font = self._font(obj)
            metrics = QFontMetricsF(font)
            text = str(obj.data.get('text', obj.label or 'Text'))
            # Text outlines also make picking rotated and multiline text precise.
            textpath = QPainterPath()
            for index, line in enumerate(text.split('\n')):
                width = metrics.horizontalAdvance(line)
                align = obj.style.get('align', 'left')
                offset = -width / 2 if align == 'center' else -width if align == 'right' else 0
                textpath.addText(offset, index * metrics.lineSpacing(), font, line)
            from PySide6.QtGui import QTransform
            transform = QTransform().translate(p.x(), p.y()).rotate(float(obj.style.get('rotation', 0)))
            path = transform.map(textpath)
        elif obj.kind == 'curve' and len(obj.points) >= 3:
            points = obj.points
            path.moveTo(self._point(points[0]))
            for i in range(len(points) - 1):
                a, b, c, d = points[max(0, i - 1)], points[i], points[i + 1], points[min(len(points) - 1, i + 2)]
                first = (b[0] + (c[0] - a[0]) / 6, b[1] + (c[1] - a[1]) / 6)
                second = (c[0] - (d[0] - b[0]) / 6, c[1] - (d[1] - b[1]) / 6)
                path.cubicTo(self._point(first), self._point(second), self._point(c))
        else:
            for segment in self.object_segments(obj):
                path.addPath(self._path_from(segment))
        return path

    @staticmethod
    def _font(obj):
        font = QFont(str(obj.style.get('font', 'Arial')))
        font.setPixelSize(max(6, int(obj.style.get('font_size', 14))))
        font.setBold(bool(obj.style.get('bold', False)))
        font.setItalic(bool(obj.style.get('italic', False)))
        return font

    def _marker(self, painter, p, obj):
        size = max(1, float(obj.style.get('marker_size', 6)))
        shape = obj.style.get('marker', 'circle')
        if shape == 'square':
            painter.drawRect(QRectF(p.x() - size, p.y() - size, size * 2, size * 2))
        elif shape in ('diamond', 'triangle'):
            coords = [(0, -size), (size, 0), (0, size), (-size, 0)] if shape == 'diamond' else [(0, -size), (size, size), (-size, size)]
            painter.drawPolygon(QPolygonF([QPointF(p.x() + x, p.y() + y) for x, y in coords]))
        elif shape == 'cross':
            painter.drawLine(QPointF(p.x() - size, p.y() - size), QPointF(p.x() + size, p.y() + size))
            painter.drawLine(QPointF(p.x() - size, p.y() + size), QPointF(p.x() + size, p.y() - size))
        else:
            painter.drawEllipse(p, size, size)

    def _draw_object(self, painter, obj, labels):
        painter.save()
        style = obj.style
        color = style.get('color', '#2459ad')
        painter.setOpacity(max(0, min(1, float(style.get('opacity', 1)))))
        painter.setPen(pen(color, style.get('width', 2), style.get('line_style', 'solid')))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if obj.kind in ('point', 'scatter'):
            painter.setBrush(QColor(style.get('fill', color)))
            points = obj.points if obj.kind == 'point' else obj.data.get('rows', [])
            for index, point in enumerate(points):
                p = self._point(point)
                if self.plot.adjusted(-20, -20, 20, 20).contains(p):
                    self._marker(painter, p, obj)
                    if labels and obj.kind == 'scatter' and obj.data.get('point_labels'):
                        painter.setFont(self._font(obj))
                        painter.drawText(p + QPointF(7, -8), str(index + 1))
        elif obj.kind == 'text' and obj.points:
            p = self._point(obj.points[0])
            painter.translate(p)
            painter.rotate(float(style.get('rotation', 0)))
            painter.setFont(self._font(obj))
            text = str(obj.data.get('text', obj.label or 'Text'))
            metrics = QFontMetricsF(painter.font())
            align = style.get('align', 'left')
            bg = style.get('background', 'transparent')
            for index, line in enumerate(text.split('\n')):
                width = metrics.horizontalAdvance(line)
                offset = -width / 2 if align == 'center' else -width if align == 'right' else 0
                y = index * metrics.lineSpacing()
                if bg and bg != 'transparent':
                    painter.fillRect(QRectF(offset - 3, y - metrics.ascent() - 2, width + 6, metrics.height() + 4), QColor(bg))
                painter.drawText(QPointF(offset, y), line)
        else:
            path = self.object_path(obj)
            painter.drawPath(path)
            if obj.kind == 'arrow' and len(obj.points) >= 2:
                start, end = self.transform.forward(obj.points[0]), self.transform.forward(obj.points[-1])
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color))
                if style.get('arrow_end', True):
                    painter.drawPolygon(arrow_head(start, end, style.get('arrow_size', 12)))
                if style.get('arrow_start', False):
                    painter.drawPolygon(arrow_head(end, start, style.get('arrow_size', 12)))
        painter.restore()
        if labels and obj.kind != 'text':
            self._draw_label(painter, obj)

    def _draw_label(self, painter, obj):
        label = obj.label
        if obj.kind == 'point' and obj.points:
            mode = obj.data.get('label_mode', 'name')
            coords = f'({obj.points[0][0]:g}, {obj.points[0][1]:g})'
            label = coords if mode == 'coordinates' else f'{label} {coords}'.strip() if mode == 'both' else label
        if not label or not obj.data.get('label_visible', True):
            return
        position = obj.data.get('label_position')
        if position is None:
            if obj.points:
                position = obj.points[-1]
            elif obj.kind == 'function':
                segments = self.object_segments(obj)
                valid = [p for s in segments for p in s if self.bounds[2] <= p[1] <= self.bounds[3]]
                position = valid[int(len(valid) * .85)] if valid else None
            elif obj.kind == 'scatter' and obj.data.get('rows'):
                position = obj.data['rows'][-1]
            elif obj.kind == 'regression':
                segments = self.object_segments(obj)
                position = segments[0][0] if segments else None
        if position is None:
            return
        p = self._point(position)
        if not self.rect.adjusted(-30, -30, 30, 30).contains(p):
            return
        painter.save()
        painter.setFont(self._font(obj))
        painter.setOpacity(max(0, min(1, float(obj.style.get('opacity', 1)))))
        painter.setPen(QColor(obj.style.get('color', '#2459ad')))
        painter.drawText(p + QPointF(8, -9), str(label))
        painter.restore()

    def _interval(self, axis):
        major = axis.major
        if major and major > 0:
            return float(major)
        # Automatic tick density follows the visible viewport after zoom/pan,
        # while manually chosen intervals remain document settings.
        span = self.bounds[1] - self.bounds[0] if axis is self.document.x_axis else self.bounds[3] - self.bounds[2]
        return nice_interval(span)

    def _axis_ticks(self, axis, low, high, minor=False):
        interval = axis.minor if minor else self._interval(axis)
        if not interval or interval <= 0:
            return []
        return ticks(low, high, interval, limit=1000)

    @staticmethod
    def _number(value, axis):
        if abs(value) < 1e-12:
            return '0'
        mode = axis.number_format
        if mode == 'scientific':
            return f'{value:.{axis.decimals}e}'
        if mode == 'decimal':
            return f'{value:.{axis.decimals}f}'
        if mode == 'pi':
            from fractions import Fraction
            f = Fraction(value / math.pi).limit_denominator(24)
            if abs(float(f) * math.pi - value) < 1e-6:
                numerator = '−' if f.numerator == -1 else '' if f.numerator == 1 else str(f.numerator)
                return f'{numerator}π' + (f'/{f.denominator}' if f.denominator != 1 else '')
        return f'{value:.6g}'

    def _draw_grid(self, painter, minor=False):
        xmin, xmax, ymin, ymax = self.bounds
        painter.setPen(pen('#eff2f5' if minor else '#e0e6ec', .6 if minor else .8))
        for x in self._axis_ticks(self.document.x_axis, xmin, xmax, minor):
            if abs(x) > 1e-12:
                painter.drawLine(self._point((x, ymin)), self._point((x, ymax)))
        for y in self._axis_ticks(self.document.y_axis, ymin, ymax, minor):
            if abs(y) > 1e-12:
                painter.drawLine(self._point((xmin, y)), self._point((xmax, y)))

    def _draw_axes(self, painter, labels=True):
        xmin, xmax, ymin, ymax = self.bounds
        doc = self.document
        xaxis, yaxis = doc.x_axis, doc.y_axis
        yzero = xaxis.position
        xzero = yaxis.position
        painter.setFont(axis_font(12))
        for horizontal, axis in ((True, xaxis), (False, yaxis)):
            if not axis.visible:
                continue
            if horizontal and not ymin <= yzero <= ymax:
                continue
            if not horizontal and not xmin <= xzero <= xmax:
                continue
            lo, hi = (xmin, xmax) if horizontal else (ymin, ymax)
            cross = xzero if horizontal else yzero
            if not axis.negative:
                lo = max(lo, cross)
            if not axis.positive:
                hi = min(hi, cross)
            if lo > hi:
                continue
            a = self.transform.forward((lo, yzero) if horizontal else (xzero, lo))
            b = self.transform.forward((hi, yzero) if horizontal else (xzero, hi))
            painter.setPen(pen('#3f4b5c', axis.width, axis.line_style))
            painter.drawLine(QPointF(*a), QPointF(*b))
            painter.setBrush(QColor('#3f4b5c'))
            if axis.arrowheads in ('positive', 'both'):
                painter.drawPolygon(arrow_head(a, b, 9))
            if axis.arrowheads in ('negative', 'both'):
                painter.drawPolygon(arrow_head(b, a, 9))
            painter.setPen(pen('#637084', .9))
            if axis.ticks and axis.minor > 0:
                major = self._interval(axis)
                for value in self._axis_ticks(axis, lo, hi, minor=True):
                    # Minor ticks have a shorter stroke and no numerical label.
                    if abs(value - cross) < 1e-10 or abs(value / major - round(value / major)) < 1e-7:
                        continue
                    p = self._point((value, yzero) if horizontal else (xzero, value))
                    painter.drawLine(p + QPointF(0, -1.7) if horizontal else p + QPointF(-1.7, 0),
                                     p + QPointF(0, 1.7) if horizontal else p + QPointF(1.7, 0))
            for value in self._axis_ticks(axis, lo, hi):
                if abs(value - cross) < 1e-10:
                    continue
                p = self._point((value, yzero) if horizontal else (xzero, value))
                if axis.ticks:
                    painter.drawLine(p + QPointF(0, -3) if horizontal else p + QPointF(-3, 0),
                                     p + QPointF(0, 3) if horizontal else p + QPointF(3, 0))
                if axis.numbers and labels:
                    text = self._number(value, axis)
                    w = painter.fontMetrics().horizontalAdvance(text)
                    if horizontal:
                        above = axis.label_side in ('above', 'positive')
                        painter.drawText(p + QPointF(-w / 2, -9 if above else 21), text)
                    else:
                        right = axis.label_side in ('right', 'positive')
                        painter.drawText(p + QPointF(9 if right else -w - 9, 4), text)
            if axis.title_visible and axis.title and labels:
                titlefont = axis_font(14)
                titlefont.setWeight(QFont.Weight.Medium)
                painter.setFont(titlefont)
                painter.setPen(QColor('#273749'))
                if horizontal:
                    painter.drawText(QRectF(self.plot.left(), self.plot.bottom() + 36, self.plot.width(), 25),
                                     Qt.AlignmentFlag.AlignCenter, axis.title)
                else:
                    painter.save()
                    painter.translate(self.rect.left() + 17, self.plot.center().y())
                    painter.rotate(-90)
                    painter.drawText(QRectF(-self.plot.height() / 2, -12, self.plot.height(), 25),
                                     Qt.AlignmentFlag.AlignCenter, axis.title)
                    painter.restore()
                painter.setFont(axis_font(12))
        origin = self._point((yaxis.position, xaxis.position))
        if self.plot.contains(origin):
            painter.setPen(QColor('#637084'))
            if doc.origin_visible:
                painter.setBrush(QColor('#637084'))
                painter.drawEllipse(origin, 2.6, 2.6)
            if doc.origin_label and labels:
                painter.drawText(origin + QPointF(-14, 18), '0')

    def draw(self, painter: QPainter, selection=None, handles=False, axes=True, grid=True,
             labels=True, background=QColor('white')):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if background is not None and QColor(background).alpha() > 0:
            painter.fillRect(self.rect, QColor(background))
        painter.save()
        painter.setClipRect(self.plot)
        if grid:
            if self.document.grid_minor:
                self._draw_grid(painter, True)
            if self.document.grid_major:
                self._draw_grid(painter, False)
        painter.restore()
        if axes:
            self._draw_axes(painter, labels)
        for obj in self.document.objects:
            if self.visible(obj):
                painter.save()
                # User text may deliberately label the outside of an axis.
                painter.setClipRect(self.rect if obj.kind == 'text' else self.plot.adjusted(-12, -12, 12, 12))
                self._draw_object(painter, obj, False)
                painter.restore()
        if labels and self.document.labels_visible:
            for obj in self.document.objects:
                if obj.kind != 'text' and self.visible(obj):
                    self._draw_label(painter, obj)
        if selection:
            self._draw_selection(painter, selection, handles)
        painter.restore()

    def _draw_selection(self, painter, selected, handles):
        painter.save()
        painter.setPen(pen('#168da2', 1.2, 'dashed'))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for obj in self.document.objects:
            if obj.id not in selected or not self.visible(obj):
                continue
            box = self.object_path(obj).boundingRect().adjusted(-6, -6, 6, 6)
            painter.drawRect(box)
            if handles and not obj.locked:
                painter.setPen(pen('#168da2', 1.2))
                painter.setBrush(QColor('white'))
                points = obj.points if obj.kind not in ('function', 'regression') else []
                for p in points:
                    screen = self._point(p)
                    painter.drawRect(QRectF(screen.x() - 3.5, screen.y() - 3.5, 7, 7))
                painter.setPen(pen('#168da2', 1.2, 'dashed'))
                painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.restore()
