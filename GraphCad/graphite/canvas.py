"""Native vector canvas with graph-space editing and transaction boundaries."""
from __future__ import annotations

import copy
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPathStroker, QPen
from PySide6.QtWidgets import QWidget, QInputDialog
from .model import GraphObject
from .geometry import constrain_endpoint, line_geometry, project_point_to_line
from .render import Renderer, pen


class GraphCanvas(QWidget):
    transactionCompleted = Signal(object, str)
    selectionChanged = Signal(object)
    cursorMoved = Signal(float, float)
    toolChanged = Signal(str)
    constraintChanged = Signal(str)
    message = Signal(str)

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.selected = set()
        self.tool = 'select'
        self.constraint_mode = 'free'
        self.constraint_angle = 0.0
        self.angle_increment = 45.0
        self.constraint_reference_id = None
        self.bounds = self.document_bounds()
        self.setMinimumSize(320, 250)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._space = False
        self._pan_last = None
        self._start = None
        self._cursor_world = None
        self._vertices = []
        self._drag_before = None
        self._drag_screen = None
        self._original = {}
        self._handle = None
        self._marquee_start = None
        self._marquee_end = None
        self._snap_position = None
        self._snap_target_id = None
        self._snap_kind = None
        self._snap_message_key = None
        self._renderer = None
        self.setAccessibleName('Graph drawing canvas')
        self.setToolTip('Wheel: zoom · Middle drag or Space+drag: pan · Shift+click: multiple selection')

    def document_bounds(self):
        return (self.document.x_axis.minimum, self.document.x_axis.maximum,
                self.document.y_axis.minimum, self.document.y_axis.maximum)

    def set_document(self, document):
        # Roll back an unfinished gesture against its original document before
        # replacing references (undo/open may reuse the same object IDs).
        self.cancel_drawing()
        self.document = document
        self.selected = set()
        self.bounds = self.document_bounds()
        if self.constraint_reference_id and self.document.get(self.constraint_reference_id) is None:
            self.constraint_reference_id = None
            self.constraint_mode = 'free'
            self.constraintChanged.emit('free')
        self.selectionChanged.emit(self.selected)
        self.update()

    def set_tool(self, tool):
        self.cancel_drawing()
        self.tool = tool
        self.setCursor(Qt.CursorShape.OpenHandCursor if tool == 'pan' else
                       Qt.CursorShape.ArrowCursor if tool == 'select' else Qt.CursorShape.CrossCursor)
        self.toolChanged.emit(tool)
        messages = {'curve': 'Curve: click control points; double-click or Enter to finish. Escape cancels.',
                    'polyline': 'Polyline: click vertices; double-click or Enter to finish. Escape cancels.',
                    'arrow': 'Arrow: drag from its start to its endpoint.',
                    'select': 'Select: click an object, drag to move, or drag a handle to edit. Shift adds objects.'}
        self.message.emit(messages.get(tool, f'{tool.replace("_", " ").title()}: click or drag on the graph.'))
        self.update()

    def set_constraint(self, mode, angle_degrees=0, increment_degrees=45, reference_id=None):
        modes = {'free', 'horizontal', 'vertical', 'parallel', 'perpendicular', 'angular', 'angle'}
        if mode not in modes:
            raise ValueError('Unknown drawing constraint')
        angle, increment = float(angle_degrees), float(increment_degrees)
        if not math.isfinite(angle) or not math.isfinite(increment) or not 0 < increment <= 360:
            raise ValueError('Angles must be finite; the increment must be greater than 0 and at most 360 degrees.')
        if mode in ('parallel', 'perpendicular'):
            reference = self.document.get(reference_id)
            geometry = line_geometry(reference) if reference is not None else None
            if geometry is None or math.dist(geometry[0], geometry[1]) <= 1e-12:
                raise ValueError('Choose an existing nondegenerate straight line as the reference.')
        self.constraint_mode = mode
        self.constraint_angle = angle
        self.angle_increment = increment
        self.constraint_reference_id = reference_id
        self._clear_snap()
        self.constraintChanged.emit(mode)
        self.message.emit('Drawing constraint: ' + mode.replace('_', ' '))
        self.update()

    def set_bounds(self, bounds):
        values = tuple(float(v) for v in bounds)
        if len(values) == 4 and all(math.isfinite(v) for v in values) and values[0] < values[1] and values[2] < values[3]:
            self.bounds = values
            self.update()

    def fit_view(self):
        self.bounds = self.document_bounds()
        self.update()

    def zoom(self, factor, anchor=None):
        factor = max(.2, min(5, float(factor)))
        xmin, xmax, ymin, ymax = self.bounds
        ax, ay = anchor or ((xmin + xmax) / 2, (ymin + ymax) / 2)
        if 1e-8 < (xmax - xmin) / factor < 1e12 and 1e-8 < (ymax - ymin) / factor < 1e12:
            self.bounds = (ax + (xmin - ax) / factor, ax + (xmax - ax) / factor,
                           ay + (ymin - ay) / factor, ay + (ymax - ay) / factor)
            self.update()

    def renderer(self):
        return Renderer(self.document, QRectF(self.rect()), self.bounds)

    def paintEvent(self, event):
        painter = QPainter(self)
        renderer = self.renderer()
        self._renderer = renderer
        renderer.draw(painter, selection=self.selected, handles=self.tool == 'select', background=QColor('white'))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._start and self._cursor_world and self.tool in ('line', 'arrow', 'infinite_line', 'horizontal', 'vertical', 'construction'):
            end = self._constrain(self._start, self._cursor_world)
            preview = GraphObject(kind=self.tool, points=[list(self._start), list(end)])
            preview.style.update({'color': '#168da2', 'line_style': 'dashed'})
            renderer._draw_object(painter, preview, False)
        if self._vertices:
            points = self._vertices + ([self._cursor_world] if self._cursor_world else [])
            preview = GraphObject(kind=self.tool, points=[list(p) for p in points])
            preview.style.update({'color': '#168da2', 'line_style': 'dashed'})
            renderer._draw_object(painter, preview, False)
            painter.setPen(pen('#168da2', 1))
            painter.setBrush(QColor('white'))
            for vertex in self._vertices:
                p = renderer._point(vertex)
                painter.drawEllipse(p, 3, 3)
        if self._marquee_start is not None and self._marquee_end is not None:
            painter.setPen(pen('#168da2', 1, 'dashed'))
            painter.setBrush(QColor(22, 141, 162, 18))
            painter.drawRect(QRectF(self._marquee_start, self._marquee_end).normalized())
        if self._snap_target_id:
            target = self.document.get(self._snap_target_id)
            if target is not None and renderer.visible(target):
                painter.save()
                painter.setClipRect(renderer.plot.adjusted(-12, -12, 12, 12))
                painter.setPen(pen('#c08621', 3.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(renderer.object_path(target))
                painter.restore()
        if self._snap_position:
            p = renderer._point(self._snap_position)
            painter.setPen(pen('#c08621', 1.3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(p.x() - 5, p.y() - 5, 10, 10))
        painter.end()

    def _world(self, pos):
        return self.renderer().transform.inverse((pos.x(), pos.y()))

    def _clear_snap(self):
        had_target = self._snap_message_key is not None
        self._snap_position = None
        self._snap_target_id = None
        self._snap_kind = None
        self._snap_message_key = None
        if had_target:
            self.message.emit('')

    def _activate_snap(self, position, target_id=None, kind='grid'):
        self._snap_position = tuple(position)
        self._snap_target_id = target_id
        self._snap_kind = kind
        key = (target_id, kind)
        if key != self._snap_message_key:
            self._snap_message_key = key
            target = self.document.get(target_id) if target_id else None
            label = (': ' + (target.name or target.kind)) if target else ''
            self.message.emit('Snap to ' + kind + label)
        return self._snap_position

    def _snap_ignored(self, ignore):
        # Exclude the dragged geometry and its complete derived closure. A foot
        # following the dragged point must never become its own snap anchor.
        ignored = set(ignore or ())
        changed = True
        while changed:
            changed = False
            for obj in self.document.objects:
                if obj.id in ignored:
                    continue
                dependency = obj.data.get('perpendicular', {})
                if isinstance(dependency, dict) and any(dependency.get(key) in ignored for key in ('source_id', 'target_id')):
                    ignored.add(obj.id)
                    changed = True
        return ignored

    def _moving_point(self):
        return len(self._original) == 1 and next(iter(self._original.values())).kind == 'point'

    def _snap(self, world, ignore=None, point_to_line=None):
        renderer = self.renderer()
        screen = renderer.transform.forward(world)
        ignored = self._snap_ignored(ignore)
        tolerance = float(getattr(self.document, 'snap_tolerance_pixels', 10))
        candidate, target_id, kind = None, None, None
        best = tolerance
        if self.document.snap_points:
            for obj in self.document.objects:
                if obj.id in ignored or not renderer.visible(obj):
                    continue
                points = obj.points + (obj.data.get('rows', []) if obj.kind == 'scatter' else [])
                for point in points:
                    q = renderer.transform.forward(point)
                    distance = math.hypot(screen[0] - q[0], screen[1] - q[1])
                    if distance <= best:
                        best, candidate, target_id, kind = distance, tuple(point), obj.id, 'point'
        if self.document.snap_intersections:
            segments = []
            for obj in self.document.objects:
                if obj.id in ignored or not renderer.visible(obj) or obj.kind in ('point', 'scatter', 'text'):
                    continue
                for points in renderer.object_segments(obj):
                    segments.extend(zip(points[:-1], points[1:]))
            segments = segments[:240]
            for index, (a, b) in enumerate(segments):
                for c, d in segments[index + 1:]:
                    dx1, dy1, dx2, dy2 = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
                    determinant = dx1 * dy2 - dy1 * dx2
                    if abs(determinant) < 1e-14:
                        continue
                    t = ((c[0] - a[0]) * dy2 - (c[1] - a[1]) * dx2) / determinant
                    u = ((c[0] - a[0]) * dy1 - (c[1] - a[1]) * dx1) / determinant
                    if 0 <= t <= 1 and 0 <= u <= 1:
                        point = (a[0] + t * dx1, a[1] + t * dy1)
                        q = renderer.transform.forward(point)
                        distance = math.hypot(screen[0] - q[0], screen[1] - q[1])
                        if distance <= best:
                            best, candidate, target_id, kind = distance, point, None, 'intersection'
        # Preserve endpoint/intersection priority before considering a line's
        # interior. Line snapping belongs to point placement and point motion.
        use_lines = (self.tool == 'point' or self._moving_point()) if point_to_line is None else point_to_line
        if candidate is None and use_lines and getattr(self.document, 'snap_lines', False):
            best = tolerance
            for obj in self.document.objects:
                if obj.id in ignored or not renderer.visible(obj):
                    continue
                geometry = line_geometry(obj)
                edges = [geometry] if geometry else [(a, b, False) for a, b in zip(obj.points[:-1], obj.points[1:])] if obj.kind == 'polyline' else []
                for a, b, infinite in edges:
                    try:
                        point = project_point_to_line(world, a, b, clamp=not infinite)
                    except ValueError:
                        continue
                    q = renderer.transform.forward(point)
                    distance = math.hypot(screen[0] - q[0], screen[1] - q[1])
                    if distance <= best:
                        best, candidate, target_id, kind = distance, point, obj.id, 'line'
        if candidate is not None:
            return self._activate_snap(candidate, target_id, kind)
        if self.document.snap_grid and self.document.snap_interval > 0:
            interval = self.document.snap_interval
            candidate = tuple(round(v / interval) * interval for v in world)
            return self._activate_snap(candidate)
        self._clear_snap()
        return tuple(world)

    def _emit_selection(self):
        self.selectionChanged.emit(set(self.selected))
        self.update()

    def _hit(self, pos):
        renderer = self.renderer()
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        for obj in reversed(self.document.objects):
            if not renderer.visible(obj):
                continue
            path = renderer.object_path(obj)
            if path.contains(pos) or stroker.createStroke(path).contains(pos):
                return obj
        return None

    def _hit_handle(self, pos):
        if len(self.selected) != 1:
            return None
        renderer = self.renderer()
        for obj in reversed(self.document.objects):
            if obj.id not in self.selected or obj.locked or not renderer.visible(obj):
                continue
            for i, point in enumerate(obj.points):
                p = renderer._point(point)
                if math.hypot(p.x() - pos.x(), p.y() - pos.y()) <= 8:
                    return obj.id, i
        return None

    def _add(self, kind, points, data=None):
        before = self.document.to_dict()
        names = {obj.name for obj in self.document.objects}
        stem = kind.replace('_', ' ').title().replace(' ', '')
        count = 1
        while f'{stem}{count}' in names:
            count += 1
        obj = GraphObject(kind=kind, points=[list(p) for p in points], name=f'{stem}{count}')
        if data:
            obj.data.update(data)
        if kind == 'point':
            obj.label = f'P{count}'
            obj.style['fill'] = obj.style.get('color', '#2459ad')
        if kind == 'construction':
            obj.style.update({'line_style': 'dashed', 'color': '#7b8594', 'width': 1.2})
        self.document.objects.append(obj)
        self.document.update_constructions()
        self.selected = {obj.id}
        self.transactionCompleted.emit(before, f'Create {kind.replace("_", " ")}')
        self._emit_selection()
        return obj

    def _constrain(self, start, end, kind=None):
        kind = kind or self.tool
        mode = 'horizontal' if kind == 'horizontal' else 'vertical' if kind == 'vertical' else self.constraint_mode
        if kind not in ('line', 'segment', 'infinite_line', 'horizontal', 'vertical', 'arrow', 'construction'):
            return tuple(end)
        reference = self._original.get(self.constraint_reference_id) or self.document.get(self.constraint_reference_id)
        if mode in ('parallel', 'perpendicular'):
            geometry = line_geometry(reference) if reference is not None else None
            if geometry is None or math.dist(geometry[0], geometry[1]) <= 1e-12:
                self.set_constraint('free')
                self.message.emit('Reference unavailable or has no direction; orientation reset to Free angle.')
                return tuple(end)
        target = constrain_endpoint(start, end, mode, self.constraint_angle, self.angle_increment, reference)
        # The constraint is the final authority. An off-constraint endpoint/grid
        # candidate must not leave a misleading active snap marker behind.
        if self._snap_position is not None and math.dist(target, self._snap_position) > 1e-10:
            self._clear_snap()
        return target

    def _drawing_target(self, world):
        return self._constrain(self._start, self._snap(world, point_to_line=False))

    def mousePressEvent(self, event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = event.position()
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and (self.tool == 'pan' or self._space)):
            self._pan_last = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            if event.button() == Qt.MouseButton.RightButton:
                self.cancel_drawing()
            return
        world = self._snap(self._world(pos))
        self._cursor_world = world
        if self.tool == 'select':
            self._handle = self._hit_handle(pos)
            hit = next((o for o in self.document.objects if self._handle and o.id == self._handle[0]), None) or self._hit(pos)
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if hit:
                related = {o.id for o in self.document.objects if hit.group and o.group == hit.group} or {hit.id}
                if shift:
                    self.selected.symmetric_difference_update(related)
                elif hit.id not in self.selected:
                    self.selected = related
                self._emit_selection()
                if hit.id in self.selected and not hit.locked:
                    self._start = self._world(pos)
                    self._drag_before = self.document.to_dict()
                    self._drag_screen = QPointF(pos)
                    self._original = {o.id: copy.deepcopy(o) for o in self.document.objects if o.id in self.selected and not o.locked}
            else:
                if not shift:
                    self.selected.clear()
                self._marquee_start = pos
                self._marquee_end = pos
                self._emit_selection()
        elif self.tool == 'point':
            self._add('point', [world])
        elif self.tool == 'text':
            text, ok = QInputDialog.getMultiLineText(self, 'Add text', 'Text', '')
            if ok and text:
                self._add('text', [world], {'text': text})
        elif self.tool in ('polyline', 'curve'):
            if not self._vertices or math.dist(world, self._vertices[-1]) > 1e-10:
                self._vertices.append(world)
            self.update()
        else:
            self._start = world
            self.update()
        event.accept()

    def _move_selected(self, delta):
        dx, dy = delta
        for obj in self.document.objects:
            original = self._original.get(obj.id)
            if original is None:
                continue
            if self._handle and obj.id == self._handle[0]:
                index = self._handle[1]
                target = [original.points[index][0] + dx, original.points[index][1] + dy]
                if len(original.points) == 2 and obj.kind in ('line', 'segment', 'infinite_line', 'horizontal', 'vertical', 'arrow', 'construction'):
                    target = self._constrain(original.points[1 - index], target, obj.kind)
                obj.points[index] = list(target)
                continue
            obj.points = [[p[0] + dx, p[1] + dy] for p in original.points]
            if obj.kind == 'scatter':
                obj.data['rows'] = [[p[0] + dx, p[1] + dy] for p in original.data.get('rows', [])]
            if obj.kind == 'function':
                obj.data['offset_x'] = original.data.get('offset_x', 0) + dx
                obj.data['offset_y'] = original.data.get('offset_y', 0) + dy
            if 'label_position' in original.data:
                p = original.data['label_position']
                obj.data['label_position'] = [p[0] + dx, p[1] + dy]
        self.document.update_constructions()

    def _drag_delta(self, world):
        if self._handle:
            original = self._original[self._handle[0]].points[self._handle[1]]
            target = self._snap(world, self.selected)
            return target[0] - original[0], target[1] - original[1]
        delta = world[0] - self._start[0], world[1] - self._start[1]
        anchor = next((obj.points[0] for obj in self._original.values() if obj.points), None)
        if anchor:
            target = self._snap((anchor[0] + delta[0], anchor[1] + delta[1]), self.selected)
            delta = target[0] - anchor[0], target[1] - anchor[1]
        return delta

    def mouseMoveEvent(self, event):
        pos = event.position()
        world = self._world(pos)
        self.cursorMoved.emit(*world)
        if self._pan_last is not None:
            delta = pos - self._pan_last
            plot = self.renderer().plot
            xmin, xmax, ymin, ymax = self.bounds
            dx, dy = -delta.x() / plot.width() * (xmax - xmin), delta.y() / plot.height() * (ymax - ymin)
            self.bounds = xmin + dx, xmax + dx, ymin + dy, ymax + dy
            self._pan_last = pos
        elif self.tool == 'select' and self._drag_before is not None and self._start is not None:
            if self._drag_screen is not None and (pos - self._drag_screen).manhattanLength() >= 2:
                self._move_selected(self._drag_delta(world))
        elif self._marquee_start is not None:
            self._marquee_end = pos
        else:
            self._cursor_world = self._drawing_target(world) if self._start and self.tool in ('line', 'arrow', 'infinite_line', 'horizontal', 'vertical', 'construction') else self._snap(world)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._pan_last is not None:
            self._pan_last = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.tool == 'pan' or self._space else Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_before is not None:
            # Release position is authoritative, including native tests that coalesce moves.
            world = self._world(event.position())
            if self._start is not None and self._drag_screen is not None and (event.position() - self._drag_screen).manhattanLength() >= 2:
                self._move_selected(self._drag_delta(world))
            before = self._drag_before
            self._drag_before = None
            if before != self.document.to_dict():
                self.transactionCompleted.emit(before, 'Edit geometry' if self._handle else 'Move objects')
                self.selectionChanged.emit(set(self.selected))
        elif self._marquee_start is not None:
            rect = QRectF(self._marquee_start, event.position()).normalized()
            if rect.width() > 3 or rect.height() > 3:
                renderer = self.renderer()
                for obj in self.document.objects:
                    if renderer.visible(obj) and rect.intersects(renderer.object_path(obj).boundingRect().adjusted(-3, -3, 3, 3)):
                        self.selected.add(obj.id)
                self._emit_selection()
            self._marquee_start = self._marquee_end = None
        elif self._start and self.tool in ('line', 'arrow', 'infinite_line', 'horizontal', 'vertical', 'construction'):
            end = self._drawing_target(self._world(event.position()))
            if math.dist(self._start, end) > 1e-10:
                self._add(self.tool, [self._start, end])
        self._start = None
        self._handle = None
        self._original = {}
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.tool in ('curve', 'polyline'):
            world = self._snap(self._world(event.position()))
            if not self._vertices or math.dist(world, self._vertices[-1]) > 1e-10:
                self._vertices.append(world)
            self.finish_path()
        elif self.tool == 'select':
            obj = self._hit(event.position())
            if obj and obj.kind == 'text' and not obj.locked:
                text, ok = QInputDialog.getMultiLineText(self, 'Edit text', 'Text', obj.data.get('text', ''))
                if ok:
                    before = self.document.to_dict()
                    obj.data['text'] = text
                    self.transactionCompleted.emit(before, 'Edit text')
                    self.selectionChanged.emit(set(self.selected))
                    self.update()
        event.accept()

    def finish_path(self):
        if len(self._vertices) >= 2:
            self._add(self.tool, self._vertices)
        self._vertices = []
        self._start = None
        self.update()

    def cancel_drawing(self):
        if self._drag_before is not None:
            # Restore in-place objects so the document reference remains valid.
            for index, obj in enumerate(self.document.objects):
                if obj.id in self._original:
                    self.document.objects[index] = copy.deepcopy(self._original[obj.id])
            self.document.update_constructions()
        self._vertices = []
        self._start = None
        self._drag_before = None
        self._drag_screen = None
        self._original = {}
        self._handle = None
        self._marquee_start = self._marquee_end = None
        self._clear_snap()
        self.update()

    def delete_selected(self):
        if not self.selected:
            return
        before = self.document.to_dict()
        removed = {o.id for o in self.document.objects if o.id in self.selected and not o.locked}
        self.document.objects[:] = [o for o in self.document.objects if o.id not in removed]
        # Linked regression has no meaningful geometry once its source is removed.
        self.document.objects[:] = [o for o in self.document.objects if o.kind != 'regression' or o.data.get('source_id') not in removed]
        self.selected -= removed
        self.document.update_constructions()
        if before != self.document.to_dict():
            self.transactionCompleted.emit(before, 'Delete objects')
            self._emit_selection()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif key == Qt.Key.Key_Escape:
            self.cancel_drawing()
            self.set_tool('select')
        elif key in (Qt.Key.Key_Enter, Qt.Key.Key_Return) and self._vertices:
            self.finish_path()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) and self.selected:
            before = self.document.to_dict()
            self._original = {o.id: copy.deepcopy(o) for o in self.document.objects if o.id in self.selected and not o.locked}
            step = self.document.snap_interval if self.document.snap_grid else (self.bounds[1] - self.bounds[0]) / 200
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step *= 10
            dx = -step if key == Qt.Key.Key_Left else step if key == Qt.Key.Key_Right else 0
            dy = step if key == Qt.Key.Key_Up else -step if key == Qt.Key.Key_Down else 0
            self._move_selected((dx, dy))
            self._original = {}
            if before != self.document.to_dict():
                self.transactionCompleted.emit(before, 'Nudge objects')
                self.selectionChanged.emit(set(self.selected))
                self.update()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = False
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.tool == 'pan' else Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta and not event.pixelDelta().isNull():
            delta = event.pixelDelta().y() * 2
        self.zoom(math.exp(max(-600, min(600, delta)) / 600), self._world(event.position()))
        event.accept()
