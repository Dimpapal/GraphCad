"""Native Qt interaction and vector rendering integration tests (no web runtime)."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from graphite.model import Document, GraphObject
from graphite.canvas import GraphCanvas
from graphite.render import Renderer, arrow_head


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def canvas(app):
    doc = Document()
    doc.snap_points = False
    canvas = GraphCanvas(doc)
    canvas.resize(900, 650)
    canvas.show()
    app.processEvents()
    yield canvas
    canvas.close()


def screen(canvas, point):
    x, y = canvas.renderer().transform.forward(point)
    return QPoint(round(x), round(y))


def drag(canvas, start, end):
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, start))
    QTest.mouseMove(canvas, screen(canvas, end), delay=10)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, end))


def test_paint_style_arrow_drag_direction_and_transaction(canvas):
    transactions = []
    canvas.transactionCompleted.connect(lambda before, label: transactions.append((before, label)))
    canvas.set_tool('arrow')
    drag(canvas, (2, 8), (7, 3))
    assert len(canvas.document.objects) == 1
    obj = canvas.document.objects[0]
    assert obj.kind == 'arrow'
    assert obj.points[0] == pytest.approx([2, 8], abs=.02)
    assert obj.points[1] == pytest.approx([7, 3], abs=.02)
    assert len(transactions) == 1
    assert transactions[0][0]['objects'] == []
    polygon = arrow_head((2, 8), (7, 3), 2)
    assert polygon[0] == QPointF(7, 3)


def test_click_point_then_numerical_coordinate_model_stays_stable_on_zoom(canvas):
    canvas.set_tool('point')
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (4, 7)))
    obj = canvas.document.objects[0]
    assert obj.kind == 'point'
    before = [p[:] for p in obj.points]
    canvas.zoom(3)
    canvas.set_bounds((-5, 15, -10, 10))
    assert obj.points == before
    obj.points[0] = [4.125, 7.875]
    renderer = canvas.renderer()
    assert renderer.transform.inverse(renderer.transform.forward(obj.points[0])) == pytest.approx(obj.points[0])


def test_select_move_handle_visibility_lock_and_delete(canvas):
    line = GraphObject(kind='line', points=[[2, 2], [7, 6]], name='Supply', label='S')
    canvas.document.objects.append(line)
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (4.5, 4)))
    assert canvas.selected == {line.id}
    drag(canvas, (4.5, 4), (5.5, 5))
    assert line.points[0] == pytest.approx([3, 3], abs=.03)
    assert line.points[1] == pytest.approx([8, 7], abs=.03)
    drag(canvas, line.points[1], (9, 8))
    assert line.points[1] == pytest.approx([9, 8], abs=.03)
    line.locked = True
    original = [p[:] for p in line.points]
    drag(canvas, (6, 5.5), (7, 6.5))
    assert line.points == original
    canvas.delete_selected()
    assert line in canvas.document.objects
    line.locked = False
    line.visible = False
    assert canvas._hit(QPointF(screen(canvas, (6, 5.5)))) is None
    line.visible = True
    canvas.selected = {line.id}
    canvas.delete_selected()
    assert canvas.document.objects == []


def test_curve_control_points_and_escape_cancel(canvas):
    canvas.set_tool('curve')
    for p in [(1, 1), (3, 6), (7, 8)]:
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, p))
    QTest.keyClick(canvas, Qt.Key.Key_Return)
    assert len(canvas.document.objects) == 1
    obj = canvas.document.objects[0]
    assert obj.kind == 'curve'
    assert len(obj.points) == 3
    assert canvas.renderer().object_path(obj).elementCount() > 3
    canvas.set_tool('select')
    drag(canvas, obj.points[1], (4, 5))
    assert obj.points[1] == pytest.approx([4, 5], abs=.03)
    canvas.set_tool('polyline')
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (2, 2)))
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert len(canvas.document.objects) == 1
    assert canvas.tool == 'select'


def test_polyline_finish_and_horizontal_constraint(canvas):
    canvas.set_tool('polyline')
    for p in [(1, 2), (3, 5), (5, 4)]:
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, p))
    QTest.keyClick(canvas, Qt.Key.Key_Return)
    assert canvas.document.objects[0].kind == 'polyline'
    canvas.set_tool('horizontal')
    drag(canvas, (2, 3), (8, 6))
    line = canvas.document.objects[1]
    assert line.points[0][1] == pytest.approx(line.points[1][1])


def test_renderer_vector_paths_regression_and_clean_render(app):
    doc = Document()
    scatter = GraphObject(kind='scatter', name='Observations', data={'rows': [[1, 3], [2, 5], [3, 7]]})
    regression = GraphObject(kind='regression', name='Fit', data={'source_id': scatter.id})
    function = GraphObject(kind='function', name='Demand', label='D', data={'expression': '8-x'})
    text = GraphObject(kind='text', points=[[3, 8]], data={'text': 'Price'})
    doc.objects.extend([scatter, regression, function, text])
    renderer = Renderer(doc, QRectF(0, 0, 900, 650))
    assert renderer.object_segments(regression)[0][0][1] == pytest.approx(1)
    scatter.data['rows'][2][1] = 9
    assert renderer.object_segments(regression)[0][0][1] != pytest.approx(1)
    assert renderer.object_path(function).elementCount() > 2
    image = QImage(900, 650, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.draw(painter, background=QColor('white'))
    painter.end()
    assert not image.isNull()
    assert image.pixelColor(0, 0) == QColor('white')
    assert renderer.object_path(text).elementCount() > 4


def test_grid_snapping_and_multiple_selection(canvas):
    canvas.document.snap_grid = True
    canvas.document.snap_interval = .5
    canvas.set_tool('point')
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (2.23, 3.17)))
    first = canvas.document.objects[0]
    assert first.points == [[2, 3]]
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (6.1, 7.1)))
    second = canvas.document.objects[1]
    canvas.set_tool('select')
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (2, 3)))
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=screen(canvas, (6, 7)))
    assert canvas.selected == {first.id, second.id}


def test_undo_snapshot_emitted_once_for_nudge(canvas):
    obj = GraphObject(kind='point', points=[[2, 2]])
    canvas.document.objects.append(obj)
    canvas.selected = {obj.id}
    actions = []
    canvas.transactionCompleted.connect(lambda before, label: actions.append((before, label)))
    QTest.keyClick(canvas, Qt.Key.Key_Right)
    assert len(actions) == 1
    assert obj.points[0][0] > 2


def test_clicking_selected_handle_does_not_change_coordinates(canvas):
    obj = GraphObject(kind='point', points=[[2.123456, 3.987654]])
    canvas.document.objects.append(obj)
    canvas.selected = {obj.id}
    before = canvas.document.to_dict()
    transactions = []
    canvas.transactionCompleted.connect(lambda a, b: transactions.append(b))
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, obj.points[0]))
    assert canvas.document.to_dict() == before
    assert transactions == []


def test_pan_moves_only_view_and_zoom_anchor_is_preserved(canvas):
    obj = GraphObject(kind='line', points=[[2, 2], [8, 8]])
    canvas.document.objects.append(obj)
    before = canvas.document.to_dict()
    original_bounds = canvas.bounds
    QTest.mousePress(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(400, 300))
    QTest.mouseMove(canvas, QPoint(450, 330), delay=10)
    QTest.mouseRelease(canvas, Qt.MouseButton.MiddleButton, pos=QPoint(450, 330))
    assert canvas.bounds != original_bounds
    assert canvas.document.to_dict() == before
    anchor = (3, 4)
    screen_before = canvas.renderer().transform.forward(anchor)
    canvas.zoom(1.8, anchor)
    assert canvas.renderer().transform.forward(anchor) == pytest.approx(screen_before)
    assert canvas.document.to_dict() == before


def test_grid_snap_is_applied_on_drag_release(canvas):
    canvas.document.snap_grid = True
    canvas.document.snap_interval = .5
    obj = GraphObject(kind='line', points=[[2, 2], [6, 6]])
    canvas.document.objects.append(obj)
    canvas.selected = {obj.id}
    drag(canvas, (4, 4), (5.13, 5.19))
    assert obj.points == [[3, 3], [7, 7]]


def test_multiline_text_and_true_cubic_curve(app):
    doc = Document()
    curve = GraphObject(kind='curve', points=[[1, 1], [3, 7], [8, 8]])
    text = GraphObject(kind='text', points=[[5, 5]], data={'text': 'Price\nQuantity'},
                       style={'align': 'center', 'rotation': 25})
    doc.objects.extend([curve, text])
    renderer = Renderer(doc, QRectF(0, 0, 900, 650))
    path = renderer.object_path(curve)
    assert any(path.elementAt(i).isCurveTo() for i in range(path.elementCount()))
    assert renderer.object_path(text).boundingRect().height() > 20


def rendered(document, bounds=None, grid=True):
    image = QImage(900, 650, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    Renderer(document, QRectF(0, 0, 900, 650), bounds).draw(painter, grid=grid)
    painter.end()
    return image


def test_panned_offscreen_axes_are_not_relocated_to_viewport_edges(app):
    doc = Document()
    doc.grid_major = True
    doc.grid_minor = True
    bounds = (10, 20, 10, 20)
    image = rendered(doc, bounds)
    hidden_axes = doc.clone()
    hidden_axes.x_axis.visible = hidden_axes.y_axis.visible = False
    assert image == rendered(hidden_axes, bounds)
    hidden_axes.grid_major = hidden_axes.grid_minor = False
    assert image != rendered(hidden_axes, bounds)
    # X crosses this view at y=0, but Y at x=0 is truly off-screen.
    bounds = (10, 20, -5, 5)
    image = rendered(doc, bounds)
    hidden_y = doc.clone()
    hidden_y.y_axis.visible = False
    assert image == rendered(hidden_y, bounds)


def test_minor_axis_ticks_render_without_grid_or_numeric_labels(app):
    doc = Document()
    doc.origin_visible = doc.origin_label = False
    for axis in (doc.x_axis, doc.y_axis):
        axis.numbers = axis.title_visible = False
        axis.minor = .2
    with_ticks = rendered(doc, grid=False)
    doc.x_axis.minor = doc.y_axis.minor = 0
    assert with_ticks != rendered(doc, grid=False)
    doc.x_axis.ticks = doc.y_axis.ticks = False
    no_ticks = rendered(doc, grid=False)
    doc.x_axis.minor = doc.y_axis.minor = .2
    assert no_ticks == rendered(doc, grid=False)


def test_multiple_selected_points_drag_together(canvas):
    a = GraphObject(kind='point', points=[[2, 2]])
    b = GraphObject(kind='point', points=[[5, 5]])
    canvas.document.objects.extend([a, b])
    canvas.selected = {a.id, b.id}
    drag(canvas, (2, 2), (3, 3))
    assert a.points[0] == pytest.approx([3, 3], abs=.03)
    assert b.points[0] == pytest.approx([6, 6], abs=.03)


def test_user_text_can_label_axis_from_document_margin(app):
    doc = Document()
    doc.objects.append(GraphObject(kind='text', points=[[-.35, 5]], data={'text': 'Pe'}))
    doc.objects.append(GraphObject(kind='text', points=[[5, -.35]], data={'text': 'Qe'}))
    image = rendered(doc, grid=False)
    blank = doc.clone()
    blank.objects = []
    assert image != rendered(blank, grid=False)
    renderer = Renderer(doc, QRectF(0, 0, 900, 650))
    for obj in doc.objects:
        path = renderer.object_path(obj)
        box = path.boundingRect().toAlignedRect()
        assert image.copy(box) != rendered(blank, grid=False).copy(box)


def test_automatic_tick_intervals_adapt_to_zoomed_viewport(app):
    doc = Document()
    doc.x_axis.major = doc.y_axis.major = 0
    rect = QRectF(0, 0, 900, 650)
    normal = Renderer(doc, rect)
    closer = Renderer(doc, rect, bounds=(2, 4, -1, 1))
    farther = Renderer(doc, rect, bounds=(-50, 50, -20, 20))
    assert normal._interval(doc.x_axis) == 1
    assert closer._interval(doc.x_axis) == pytest.approx(.2)
    assert farther._interval(doc.x_axis) == 10
    assert farther._interval(doc.y_axis) == 5
    values = closer._axis_ticks(doc.x_axis, 2, 4)
    positions = [closer.transform.forward((v, 0))[0] for v in values]
    assert len(values) == 11
    assert positions[1] - positions[0] == pytest.approx(closer.plot.width() / 10)
    doc.x_axis.major = .5
    assert farther._interval(doc.x_axis) == .5
