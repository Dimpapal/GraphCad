"""GraphCAD point-on-line snapping, constraints and linked construction gestures."""
import copy
import math
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from graphite.model import Document, GraphObject
from graphite.canvas import GraphCanvas
from graphite.render import Renderer
from graphite.geometry import project_point_to_line


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def canvas(app):
    document = Document()
    document.snap_grid = False
    document.snap_points = False
    document.snap_lines = True
    document.snap_tolerance_pixels = 10
    widget = GraphCanvas(document)
    widget.resize(900, 650)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def screen(canvas, point):
    x, y = canvas.renderer().transform.forward(point)
    return QPoint(round(x), round(y))


def drag(canvas, start, end):
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, start))
    QTest.mouseMove(canvas, screen(canvas, end), delay=5)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, end))


def line(canvas, kind='line', points=None):
    obj = GraphObject(kind=kind, points=points or [[1, 5], [9, 5]], name='Target line')
    canvas.document.objects.append(obj)
    return obj


def test_point_snaps_to_interior_along_entire_finite_segment(canvas):
    target = line(canvas)
    canvas.set_tool('point')
    for x in (1.3, 3.7, 5, 8.7):
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (x, 5.12)))
        point = canvas.document.objects[-1]
        assert point.kind == 'point'
        assert point.points[0][0] == pytest.approx(x, abs=.02)
        assert point.points[0][1] == pytest.approx(5)
        assert canvas._snap_target_id == target.id
        assert canvas._snap_kind == 'line'
    assert len(canvas.document.objects) == 5


@pytest.mark.parametrize('kind', ['line', 'segment', 'construction', 'arrow', 'horizontal', 'vertical', 'infinite_line', 'polyline'])
def test_supported_line_types_and_polyline_edges(canvas, kind):
    points = [[5, 1], [5, 9]] if kind == 'vertical' else [[1, 5], [9, 5]]
    if kind == 'polyline':
        points += [[9, 9]]
    target = line(canvas, kind, points)
    canvas.set_tool('point')
    near, expected = ((5.1, 4), (5, 4)) if kind == 'vertical' else ((4, 5.1), (4, 5))
    assert canvas._snap(near) == pytest.approx(expected)
    assert canvas._snap_target_id == target.id
    if kind == 'polyline':
        assert canvas._snap((8.9, 7)) == pytest.approx((9, 7))


def test_finite_extents_and_infinite_line_extension(canvas):
    target = line(canvas, points=[[3, 5], [6, 5]])
    canvas.set_tool('point')
    assert canvas._snap((8, 5.1)) == (8, 5.1)
    assert canvas._snap_target_id is None
    target.kind = 'infinite_line'
    assert canvas._snap((8, 5.1)) == pytest.approx((8, 5))
    assert canvas._snap_target_id == target.id


def test_line_snap_is_optional_and_not_applied_to_line_endpoint_tools(canvas):
    line(canvas)
    canvas.set_tool('point')
    canvas.document.snap_lines = False
    assert canvas._snap((4, 5.1)) == (4, 5.1)
    canvas.document.snap_lines = True
    canvas.set_tool('line')
    assert canvas._snap((4, 5.1)) == (4, 5.1)
    drag(canvas, (2, 2), (4, 5.1))
    assert canvas.document.objects[-1].points[1][1] == pytest.approx(5.1, abs=.02)


def test_pixel_tolerance_remains_exact_across_zoom_and_can_be_changed(canvas):
    line(canvas)
    canvas.set_tool('point')
    for bounds in ((0, 10, 0, 10), (-10, 20, -10, 20), (2, 8, 4, 6)):
        canvas.set_bounds(bounds)
        transform = canvas.renderer().transform
        dy = 1 / transform.sy
        assert canvas._snap((4, 5 + 9 * dy)) == pytest.approx((4, 5))
        outside = (4, 5 + 11 * dy)
        assert canvas._snap(outside) == pytest.approx(outside)
        assert canvas._snap_position is None
        canvas.document.snap_tolerance_pixels = 6
        inside_old_tolerance = (4, 5 + 9 * dy)
        assert canvas._snap(inside_old_tolerance) == pytest.approx(inside_old_tolerance)
        canvas.document.snap_tolerance_pixels = 10


def test_diagonal_snap_is_perpendicular_in_document_not_screen_coordinates(canvas):
    target = line(canvas, points=[[20, 2], [80, 8]])
    canvas.set_bounds((0, 100, 0, 10))
    canvas.set_tool('point')
    near = (50, 5.1)
    expected = project_point_to_line(near, target.points[0], target.points[1])
    snapped = canvas._snap(near)
    assert snapped == pytest.approx(expected)
    vector = (target.points[1][0] - target.points[0][0], target.points[1][1] - target.points[0][1])
    assert (near[0] - snapped[0]) * vector[0] + (near[1] - snapped[1]) * vector[1] == pytest.approx(0, abs=1e-11)
    transform = canvas.renderer().transform
    a, b, q = (transform.forward(p) for p in (target.points[0], target.points[1], near))
    wrong_screen_projection = transform.inverse(project_point_to_line(q, a, b))
    assert math.dist(snapped, wrong_screen_projection) > .02


def test_existing_endpoint_priority_and_moving_point_line_snap(canvas):
    target = line(canvas)
    canvas.document.snap_points = True
    canvas.set_tool('point')
    # Interior projection is closer, but explicit nearby endpoints keep priority.
    assert canvas._snap((1.07, 5.04)) == pytest.approx((1, 5))
    assert canvas._snap_kind == 'point'
    canvas.document.snap_points = False
    point = GraphObject(kind='point', points=[[3, 2]])
    canvas.document.objects.append(point)
    canvas.set_tool('select')
    canvas.selected = {point.id}
    drag(canvas, (3, 2), (4, 5.12))
    assert point.points[0] == pytest.approx((4, 5), abs=.02)
    assert canvas._snap_target_id == target.id


def test_dragged_point_and_dependent_construction_do_not_self_snap(canvas):
    point = GraphObject(kind='point', points=[[3, 3]])
    foot = GraphObject(kind='point', points=[[3, 5]], locked=True,
                       data={'perpendicular': {'role': 'foot', 'source_id': point.id, 'axis': 'x'}})
    segment = GraphObject(kind='construction', points=[[3, 3], [3, 5]], locked=True,
                          data={'perpendicular': {'role': 'segment', 'source_id': point.id, 'axis': 'x'}})
    nested = GraphObject(kind='construction', points=[[3, 5], [4, 5]], locked=True,
                         data={'perpendicular': {'role': 'segment', 'source_id': foot.id, 'axis': 'y'}})
    canvas.document.objects.extend([point, foot, segment, nested])
    canvas.document.snap_points = True
    canvas.set_tool('point')
    assert canvas._snap((3.05, 5.03), ignore={point.id}) == (3.05, 5.03)
    assert canvas._snap_target_id is None


@pytest.mark.parametrize('mode, expected_angle', [('horizontal', 0), ('vertical', 90), ('angle', 30), ('angular', 45)])
def test_constraints_apply_to_drag_creation_in_world_coordinates(canvas, mode, expected_angle):
    canvas.set_bounds((0, 20, 0, 10))
    canvas.set_constraint(mode, angle_degrees=30, increment_degrees=45)
    canvas.set_tool('arrow')
    drag(canvas, (2, 2), (7, 6.5))
    obj = canvas.document.objects[-1]
    dx, dy = obj.points[1][0] - obj.points[0][0], obj.points[1][1] - obj.points[0][1]
    assert math.degrees(math.atan2(dy, dx)) == pytest.approx(expected_angle, abs=1e-9)
    assert obj.kind == 'arrow'


def test_free_constraint_preserves_drag_and_custom_increment(canvas):
    canvas.set_tool('line')
    canvas.set_constraint('free')
    drag(canvas, (2, 2), (7, 6.5))
    free = canvas.document.objects[-1]
    assert free.points[1] == pytest.approx([7, 6.5], abs=.02)
    canvas.set_constraint('angular', increment_degrees=15)
    drag(canvas, (2, 2), (7, 5.1))
    constrained = canvas.document.objects[-1]
    dx, dy = constrained.points[1][0] - constrained.points[0][0], constrained.points[1][1] - constrained.points[0][1]
    assert math.degrees(math.atan2(dy, dx)) == pytest.approx(30)


@pytest.mark.parametrize('mode', ['parallel', 'perpendicular'])
def test_reference_constraints_have_graph_space_invariants(canvas, mode):
    reference = line(canvas, points=[[1, 1], [8, 4]])
    canvas.set_bounds((0, 20, 0, 10))
    canvas.set_constraint(mode, reference_id=reference.id)
    canvas.set_tool('construction')
    drag(canvas, (4, 2), (8, 7))
    obj = canvas.document.objects[-1]
    dx, dy = obj.points[1][0] - obj.points[0][0], obj.points[1][1] - obj.points[0][1]
    if mode == 'parallel':
        assert dx * 3 - dy * 7 == pytest.approx(0, abs=1e-10)
    else:
        assert dx * 7 + dy * 3 == pytest.approx(0, abs=1e-10)
    with pytest.raises(ValueError):
        canvas.set_constraint(mode, reference_id='missing')


def test_constraint_is_final_after_endpoint_and_grid_snapping(canvas):
    off_constraint = GraphObject(kind='point', points=[[7, 6.5]])
    canvas.document.objects.append(off_constraint)
    canvas.document.snap_points = True
    canvas.document.snap_grid = True
    canvas.document.snap_interval = .5
    canvas.set_constraint('angle', angle_degrees=30)
    canvas.set_tool('line')
    drag(canvas, (2, 2), (7, 6.5))
    obj = canvas.document.objects[-1]
    dx, dy = obj.points[1][0] - obj.points[0][0], obj.points[1][1] - obj.points[0][1]
    assert math.degrees(math.atan2(dy, dx)) == pytest.approx(30)
    assert canvas._snap_target_id is None
    assert canvas._snap_position is None


def test_endpoint_edit_constrained_about_opposite_fixed_endpoint(canvas):
    obj = line(canvas, points=[[2, 2], [7, 5]])
    canvas.set_tool('select')
    canvas.selected = {obj.id}
    canvas.set_constraint('vertical')
    original_start = copy.deepcopy(obj.points[0])
    drag(canvas, (7, 5), (8, 7))
    assert obj.points[0] == original_start
    assert obj.points[1][0] == original_start[0]
    assert obj.points[1][1] == pytest.approx(7, abs=.02)
    canvas.set_constraint('free')
    obj.kind = 'horizontal'
    obj.points = [[2, 3], [7, 3]]
    drag(canvas, (2, 3), (1, 8))
    assert obj.points[1] == [7, 3]
    assert obj.points[0] == pytest.approx([1, 3], abs=.02)


def test_snap_highlight_and_marker_exist_only_in_canvas(app, canvas):
    target = line(canvas)
    canvas.set_tool('point')
    canvas._snap((4, 5.1))
    assert canvas._snap_target_id == target.id
    canvas.update()
    app.processEvents()
    widget_image = canvas.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    clean = QImage(canvas.width(), canvas.height(), QImage.Format.Format_RGB32)
    painter = QPainter(clean)
    Renderer(canvas.document, QRectF(canvas.rect()), canvas.bounds).draw(painter, background=QColor('white'))
    painter.end()
    assert widget_image != clean
    # Overlay is not encoded in document, so any shared-renderer export stays clean.
    before = canvas.document.to_dict()
    canvas._clear_snap()
    assert canvas.document.to_dict() == before
    canvas.update()
    app.processEvents()
    assert canvas.grab().toImage().convertToFormat(QImage.Format.Format_RGB32) == clean


def test_live_perpendicular_updates_share_drag_transaction_and_cancel(canvas):
    from graphite.constructions import create_perpendicular
    from graphite.history import History
    target = line(canvas, points=[[1, 3], [9, 3]])
    source = GraphObject(kind='point', points=[[4, 8]], name='Source')
    canvas.document.objects.append(source)
    foot, segment = create_perpendicular(canvas.document, source.id, target_id=target.id)
    canvas.document.objects.extend([foot, segment])
    original = canvas.document.to_dict()
    history = History(canvas.document)
    transactions = []
    canvas.transactionCompleted.connect(lambda before, label: (transactions.append(label), history.commit(before, label)))
    canvas.set_tool('select')
    canvas.selected = {source.id}
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (4, 8)))
    QTest.mouseMove(canvas, screen(canvas, (6, 7)), delay=5)
    assert foot.points[0] == pytest.approx((6, 3), abs=.02)
    assert segment.points[0] == pytest.approx((6, 7), abs=.02)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=screen(canvas, (6, 7)))
    assert canvas.document.to_dict() == original
    assert transactions == []
    # A completed gesture records source and derived geometry atomically.
    source = canvas.document.get(source.id)
    canvas.selected = {source.id}
    drag(canvas, (4, 8), (6, 7))
    assert len(transactions) == 1
    assert canvas.document.get(foot.id).points[0] == pytest.approx((6, 3), abs=.02)
    restored = history.undo()
    assert restored.get(source.id).points == [[4, 8]]
    assert restored.get(foot.id).points == [[4, 3]]
    redone = history.redo()
    assert redone.get(foot.id).points[0] == pytest.approx((6, 3), abs=.02)
    assert redone.get(segment.id).data['perpendicular']['source_id'] == source.id


def test_target_line_edit_refreshes_derived_perpendicular_geometry(canvas):
    from graphite.constructions import create_perpendicular
    target = line(canvas, points=[[1, 3], [9, 3]])
    source = GraphObject(kind='point', points=[[4, 8]], name='Source')
    canvas.document.objects.append(source)
    foot, segment = create_perpendicular(canvas.document, source.id, target_id=target.id)
    canvas.document.objects.extend([foot, segment])
    canvas.set_tool('select')
    canvas.selected = {target.id}
    drag(canvas, (9, 3), (8, 6))
    expected = project_point_to_line(source.points[0], target.points[0], target.points[1])
    assert foot.points[0] == pytest.approx(expected)
    vector = [target.points[1][i] - target.points[0][i] for i in (0, 1)]
    perpendicular = [segment.points[1][i] - segment.points[0][i] for i in (0, 1)]
    assert vector[0] * perpendicular[0] + vector[1] * perpendicular[1] == pytest.approx(0, abs=1e-10)


def test_hidden_targets_and_degenerate_references_are_rejected(canvas):
    target = line(canvas)
    canvas.set_tool('point')
    target.visible = False
    assert canvas._snap((4, 5.1)) == (4, 5.1)
    target.visible = True
    canvas.document.type_visibility['line'] = False
    assert canvas._snap((4, 5.1)) == (4, 5.1)
    canvas.document.type_visibility['line'] = True
    target.points = [[4, 5], [4, 5]]
    assert canvas._snap((4, 5.1)) == (4, 5.1)
    with pytest.raises(ValueError):
        canvas.set_constraint('parallel', reference_id=target.id)


def test_lost_reference_explicitly_resets_constraint(app):
    from graphite.canvas import GraphCanvas
    from graphite.model import Document,GraphObject
    doc=Document();ref=GraphObject('line',[[0,0],[2,3]])
    doc.objects.append(ref);canvas=GraphCanvas(doc)
    messages=[];canvas.message.connect(messages.append)
    canvas.set_constraint('parallel',reference_id=ref.id)
    ref.points=[[1,1],[1,1]]
    assert canvas._constrain((0,0),(2,4),'line')==(2,4)
    assert canvas.constraint_mode=='free' and canvas.constraint_reference_id is None
    assert any('reset to Free' in text for text in messages)
