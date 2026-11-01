"""GraphCad extensions preserve mathematical geometry and legacy v1 projects."""
from copy import deepcopy
import math
from pathlib import Path

import pytest

from graphite.constructions import create_perpendicular, resolve_constructions
from graphite.geometry import ViewTransform, constrain_endpoint, line_geometry, project_point_to_line
from graphite.history import History
from graphite.model import Document, GraphObject


@pytest.mark.parametrize("point,a,b,expected", [
    ((3, 5), (0, 2), (10, 2), (3, 2)),
    ((3, 5), (7, -2), (7, 10), (7, 5)),
    ((5, 7), (0, 0), (2, 1), (6.8, 3.4)),
    ((5, 7), (2, 1), (0, 0), (6.8, 3.4)),
    ((-3, 4), (0, 0), (4, -4), (-3.5, 3.5)),
    ((4, 2), (0, 0), (2, 1), (4, 2)),
    ((1e-10, 3e-10), (0, 0), (0, 1e-12), (0, 3e-10)),
    ((0, 1e-4), (1e12, 0), (-1e12, 0), (0, 0)),
])
def test_projection_is_orthogonal_in_document_space(point, a, b, expected):
    foot = project_point_to_line(point, a, b)
    assert foot == pytest.approx(expected, abs=1e-25 if max(map(abs, expected)) < 1e-8 else 1e-12)
    dot = (point[0]-foot[0])*(b[0]-a[0]) + (point[1]-foot[1])*(b[1]-a[1])
    assert dot == pytest.approx(0, abs=1e-12)


def test_projection_clamps_only_when_requested_and_preserves_endpoint_values():
    assert project_point_to_line((5, 7), (0, 0), (2, 1)) == pytest.approx((6.8, 3.4))
    assert project_point_to_line((5, 7), (0, 0), (2, 1), clamp=True) == (2, 1)
    assert project_point_to_line((-3, -4), (0, 0), (2, 1), clamp=True) == (0, 0)
    assert project_point_to_line((1, 3), (0, 0), (4, 0), clamp=True) == (1, 0)
    with pytest.raises(ValueError, match="different"):
        project_point_to_line((2, 3), (1, 1), (1, 1))


@pytest.mark.parametrize("value", [(math.nan, 1), (1, math.inf), (True, 1), (1,), "12"])
def test_projection_rejects_invalid_coordinate_pairs(value):
    with pytest.raises(ValueError):
        project_point_to_line(value, (0, 0), (1, 1))


@pytest.mark.parametrize("kind,infinite", [("line", False), ("segment", False), ("construction", False),
                                          ("arrow", False), ("infinite_line", True)])
def test_straight_object_geometry_keeps_finite_extent_semantics(kind, infinite):
    obj = GraphObject(kind, [[1, 2], [7, 8]])
    assert line_geometry(obj) == ((1, 2), (7, 8), infinite)
    a, b, is_infinite = line_geometry(obj)
    foot = project_point_to_line((20, 30), a, b, clamp=not is_infinite)
    assert foot == pytest.approx((24.5, 25.5) if infinite else (7, 8))


def test_horizontal_vertical_and_unsupported_geometries():
    assert line_geometry(GraphObject("horizontal", [[1, 2], [7, 8]])) == ((1, 2), (7, 2), False)
    assert line_geometry(GraphObject("vertical", [[1, 2], [7, 8]])) == ((1, 2), (1, 8), False)
    for kind in ("point", "curve", "polyline", "function", "scatter", "text"):
        assert line_geometry(GraphObject(kind, [[1, 2], [7, 8]])) is None


def test_fixed_orientation_constraints_and_reference_forms():
    start, end = (2, 3), (9, 7)
    assert constrain_endpoint(start, end) == end
    assert constrain_endpoint(start, end, "horizontal") == (9, 3)
    assert constrain_endpoint(start, end, "vertical") == (2, 7)
    assert constrain_endpoint(start, end, "angle", angle_degrees=90) == (2, 7)
    expected_parallel = project_point_to_line(end, start, (start[0]+2, start[1]+1))
    expected_perpendicular = project_point_to_line(end, start, (start[0]-1, start[1]+2))
    for reference in (((0, 0), (2, 1)), (2, 1), GraphObject("line", [[0, 0], [2, 1]])):
        assert constrain_endpoint(start, end, "parallel", reference=reference) == pytest.approx(expected_parallel)
        assert constrain_endpoint(start, end, "perpendicular", reference=reference) == pytest.approx(expected_perpendicular)


def test_parallel_and_perpendicular_are_true_under_unequal_screen_scales():
    start, end = (1, 2), (6, 9)
    reference = ((0, 0), (4, 2))
    transform = ViewTransform((-2, 12, -2, 100), (0, 0, 1200, 500))
    target = constrain_endpoint(start, end, "perpendicular", reference=reference)
    delta = target[0]-start[0], target[1]-start[1]
    assert delta[0]*4 + delta[1]*2 == pytest.approx(0, abs=1e-12)
    # The screen image intentionally has different X/Y scales; the construction
    # must remain orthogonal in the saved document rather than chase screen pixels.
    screen_start, screen_end = transform.forward(start), transform.forward(target)
    assert not math.isclose(abs(screen_end[0]-screen_start[0]), abs(screen_end[1]-screen_start[1]))
    restored = transform.inverse(transform.forward(target))
    assert restored == pytest.approx(target)


def test_custom_angle_and_angular_increment_use_graph_radians():
    start, end = (2, 4), (8, 9)
    fixed = constrain_endpoint(start, end, "angle", angle_degrees=30)
    assert math.degrees(math.atan2(fixed[1]-4, fixed[0]-2)) == pytest.approx(30)
    snapped = constrain_endpoint(start, end, "angular", increment_degrees=45)
    assert math.degrees(math.atan2(snapped[1]-4, snapped[0]-2)) == pytest.approx(45)
    assert math.dist(start, snapped) == pytest.approx(math.dist(start, end))
    negative = constrain_endpoint((0, 0), (-2, -3), "angular", increment_degrees=90)
    assert negative == pytest.approx((0, -math.sqrt(13)))
    assert constrain_endpoint(start, start, "angular") == start


@pytest.mark.parametrize("kwargs", [{"mode": "invalid"}, {"mode": "angle", "angle_degrees": math.nan},
                                    {"mode": "angular", "increment_degrees": 0},
                                    {"mode": "parallel"}, {"mode": "perpendicular", "reference": ((1, 1), (1, 1))}])
def test_invalid_constraint_input_is_explicit(kwargs):
    with pytest.raises(ValueError):
        constrain_endpoint((0, 0), (2, 3), **kwargs)


def linked_document(source_point=(5, 7), target_points=((0, 0), (2, 1)), kind="line"):
    doc = Document()
    source = GraphObject("point", [list(source_point)], name="P", label="P")
    target = GraphObject(kind, [list(p) for p in target_points], name="Target")
    doc.objects.extend([source, target])
    helpers = create_perpendicular(doc, source.id, target.id)
    doc.objects.extend(helpers)
    return doc, source, target, helpers[0], helpers[1]


def test_linked_helpers_use_supporting_line_without_appending_or_replacing_source():
    doc = Document()
    source = GraphObject("point", [[5, 7]], name="P")
    target = GraphObject("line", [[0, 0], [2, 1]], name="Target")
    doc.objects.extend([source, target])
    foot, segment = create_perpendicular(doc, source.id, target.id)
    assert doc.objects == [source, target]
    assert foot.kind == "point" and segment.kind == "construction"
    assert foot.points[0] == pytest.approx([6.8, 3.4])
    assert segment.points[0] == [5, 7] and segment.points[1] == foot.points[0]
    assert foot.group and foot.group == segment.group
    assert foot.locked and segment.locked
    assert foot.data["perpendicular"] == {"role": "foot", "source_id": source.id, "target_id": target.id}
    assert source.points == [[5, 7]] and target.points == [[0, 0], [2, 1]]


@pytest.mark.parametrize("kind", ["line", "segment", "infinite_line", "arrow", "construction", "horizontal", "vertical"])
def test_all_straight_target_types_create_perpendiculars(kind):
    doc, source, target, foot, segment = linked_document(kind=kind)
    a, b, _ = line_geometry(target)
    assert foot.points[0] == pytest.approx(project_point_to_line(source.points[0], a, b))
    assert doc.update_constructions() == []


def test_source_on_line_allows_exact_zero_length_connector():
    doc, source, target, foot, segment = linked_document(source_point=(4, 2))
    assert foot.points == source.points
    assert segment.points[0] == segment.points[1] == source.points[0]
    doc.validate()


def test_initial_degenerate_target_and_invalid_target_errors_leave_objects_intact():
    doc = Document()
    point = GraphObject("point", [[2, 3]])
    line = GraphObject("line", [[1, 1], [1, 1]])
    doc.objects.extend([point, line])
    before = doc.to_dict()
    with pytest.raises(ValueError, match="different"):
        create_perpendicular(doc, point.id, line.id)
    assert doc.to_dict() == before
    with pytest.raises(ValueError, match="straight"):
        create_perpendicular(doc, point.id, point.id)
    with pytest.raises(ValueError):
        create_perpendicular(doc, line.id, axis="x")
    with pytest.raises(ValueError):
        create_perpendicular(doc, point.id, line.id, axis="x")


def test_live_updates_follow_source_target_and_axis_positions():
    doc, source, target, foot, segment = linked_document()
    source.points[0] = [8, 9]
    target.points = [[1, 2], [1, 5]]
    doc.update_constructions()
    assert foot.points == [[1, 9]] and segment.points == [[8, 9], [1, 9]]
    xfoot, xsegment = create_perpendicular(doc, source.id, axis="x")
    yfoot, ysegment = create_perpendicular(doc, source.id, axis="y")
    doc.objects.extend([xfoot, xsegment, yfoot, ysegment])
    doc.x_axis.position, doc.y_axis.position = 3, -2
    doc.update_constructions()
    assert xfoot.points == [[8, 3]] and xsegment.points == [[8, 9], [8, 3]]
    assert yfoot.points == [[-2, 9]] and ysegment.points == [[8, 9], [-2, 9]]
    # Axis visibility and directions do not alter the internal supporting axes.
    doc.x_axis.visible = doc.y_axis.visible = False
    doc.x_axis.positive = doc.y_axis.negative = False
    doc.update_constructions()
    assert xfoot.points == [[8, 3]] and yfoot.points == [[-2, 9]]


def test_transient_degenerate_target_freezes_then_recovers_linked_geometry():
    doc, source, target, foot, segment = linked_document()
    original = deepcopy(foot.points), deepcopy(segment.points)
    target.points = [[1, 1], [1, 1]]
    notices = doc.update_constructions()
    assert notices and all("no direction" in notice for notice in notices)
    assert (foot.points, segment.points) == original
    assert "perpendicular" in foot.data and foot.locked
    target.points = [[0, 2], [10, 2]]
    assert doc.update_constructions() == []
    assert foot.points == [[5, 2]]


@pytest.mark.parametrize("deleted", ["source", "target"])
def test_deleted_dependencies_freeze_detach_and_unlock_helpers(deleted):
    doc, source, target, foot, segment = linked_document()
    original = deepcopy(foot.points), deepcopy(segment.points)
    removed = source if deleted == "source" else target
    doc.objects.remove(removed)
    notices = doc.update_constructions()
    assert len(notices) == 2 and all("detached" in notice for notice in notices)
    assert (foot.points, segment.points) == original
    assert "perpendicular" not in foot.data and "perpendicular" not in segment.data
    assert not foot.locked and not segment.locked
    doc.validate()


def test_dependency_order_independent_and_deep_chain_iterative():
    doc = Document()
    source = GraphObject("point", [[3, 7]], name="Root")
    doc.objects.append(source)
    previous = source
    helpers = []
    for i in range(1600):
        helper = GraphObject("point", [[9, 9]], locked=True,
                             data={"perpendicular": {"role": "foot", "source_id": previous.id, "axis": "x"}})
        helpers.append(helper)
        previous = helper
    doc.objects = list(reversed(helpers)) + [source]
    doc.update_constructions()
    assert all(helper.points == [[3, 0]] for helper in helpers)
    source.points[0] = [8, 5]
    doc.update_constructions()
    assert all(helper.points == [[8, 0]] for helper in helpers)


def test_dependency_cycles_rejected_before_partial_updates():
    doc, source, target, foot, segment = linked_document()
    source.data["perpendicular"] = {"role": "foot", "source_id": foot.id, "axis": "x"}
    before = doc.to_dict()
    with pytest.raises(ValueError, match="cycles"):
        doc.update_constructions()
    assert doc.to_dict() == before
    with pytest.raises(ValueError, match="cycles"):
        doc.validate()
    with pytest.raises(ValueError, match="cycles"):
        Document.from_dict(before)


@pytest.mark.parametrize("metadata", [None, [], {}, {"role": "other", "source_id": "x", "axis": "x"},
                                      {"role": "foot", "source_id": [], "axis": "x"},
                                      {"role": "foot", "source_id": "p", "axis": "z"},
                                      {"role": "foot", "source_id": "p", "axis": "x", "target_id": "t"},
                                      {"role": "foot", "source_id": "p", "axis": "x", "arbitrary": 1}])
def test_malformed_reserved_metadata_rejected(metadata):
    obj = GraphObject("point", [[1, 2]], data={"perpendicular": metadata})
    with pytest.raises(ValueError):
        obj.validate()


def test_reserved_reference_type_validation_and_unrelated_metadata_preservation():
    doc, source, target, foot, segment = linked_document()
    foot.data["notes"] = {"arbitrary": [1, "text", True]}
    doc.update_constructions()
    assert foot.data["notes"] == {"arbitrary": [1, "text", True]}
    foot.data["perpendicular"]["source_id"] = target.id
    with pytest.raises(ValueError, match="source"):
        doc.update_constructions()


def test_save_load_and_undo_redo_materialize_identical_linked_geometry(tmp_path):
    doc, source, target, foot, segment = linked_document()
    history = History(doc)
    before = doc.to_dict()
    source.points[0] = [8, 9]
    doc.x_axis.position = 3
    doc.update_constructions()
    after = doc.to_dict()
    history.commit(before, "Move source")
    restored = history.undo()
    assert restored.to_dict() == before
    restored = history.redo()
    assert restored.to_dict() == after
    path = tmp_path / "linked.graphite"
    restored.save(path)
    assert Document.load(path).to_dict() == after
    # Repeated serialization/resolution is idempotent and does not grow metadata.
    for _ in range(5):
        restored = Document.from_dict(restored.to_dict())
        assert restored.to_dict() == after


def test_saving_resolves_stale_geometry_and_reopening_detaches_deleted_reference(tmp_path):
    doc, source, target, foot, segment = linked_document()
    source.points[0] = [4, 9]
    path = tmp_path / "stale.graphite"
    doc.save(path)
    assert foot.points[0] == pytest.approx(project_point_to_line([4, 9], *target.points))
    raw = doc.to_dict()
    raw["objects"] = [obj for obj in raw["objects"] if obj["id"] != target.id]
    restored = Document.from_dict(raw)
    assert "perpendicular" not in restored.get(foot.id).data
    assert not restored.get(foot.id).locked


def test_legacy_documents_load_without_opt_in_or_format_bump():
    # These v1 fixtures were carried over unchanged from the original project;
    # keep the test runnable from the standalone GraphCad source distribution.
    baseline = Path(__file__).resolve().parent / "fixtures" / "graphite-v1"
    projects = [baseline / name for name in ("supply-demand.graphite", "scatter-regression.graphite",
                                            "mathematics.graphite", "mixed-workflow.graphite")]
    for path in projects:
        doc = Document.load(path)
        assert doc.snap_lines is False and doc.snap_tolerance_pixels == 10
        raw = doc.to_dict()
        assert raw["version"] == 1 and raw["format"] == "graphite-document"
        raw.pop("snap_lines")
        raw.pop("snap_tolerance_pixels")
        old_shape = Document.from_dict(raw)
        assert old_shape.objects == doc.objects
        assert old_shape.bounds == doc.bounds


@pytest.mark.parametrize("value", [0, 51, math.nan, math.inf, True, "10"])
def test_snap_tolerance_is_bounded_finite_document_preference(value):
    doc = Document(snap_tolerance_pixels=value)
    with pytest.raises(ValueError):
        doc.validate()


def test_new_precision_preferences_roundtrip_and_old_defaults():
    doc = Document(snap_lines=True, snap_tolerance_pixels=7.5)
    doc.validate()
    rebuilt = Document.from_dict(doc.to_dict())
    assert rebuilt.snap_lines and rebuilt.snap_tolerance_pixels == 7.5
    assert Document().snap_lines is False and Document().snap_tolerance_pixels == 10
