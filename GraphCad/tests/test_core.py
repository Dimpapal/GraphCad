import copy
import json
import math
import pytest

from graphite.geometry import (ViewTransform, arrow_polygon, clip_line, format_number,
                               nice_interval, segment_intersection, smooth_curve, ticks)
from graphite.history import History
from graphite.model import Axis, Document, GraphObject
from graphite.templates import make_template, template_names


@pytest.mark.parametrize("bounds", [(0, 10, 0, 10), (-10, 10, -10, 10), (-2, 19, -50, 3), (.001, .01, -1e5, 1e5)])
def test_coordinate_roundtrip_independent_ranges(bounds):
    transform = ViewTransform(bounds, (72, 28, 836, 603))
    for x in [bounds[0], bounds[1], (bounds[0]+bounds[1])/2]:
        for y in [bounds[2], bounds[3], (bounds[2]+bounds[3])/2]:
            assert transform.inverse(transform.forward((x, y))) == pytest.approx((x, y))
    assert transform.forward((bounds[0], bounds[2])) == pytest.approx((72, 631))


def test_origin_position_for_asymmetric_four_quadrants():
    transform = ViewTransform((-3, 9, -2, 6), (20, 30, 1200, 800))
    assert transform.forward((0, 0)) == (320, 630)


def test_ticks_automatic_manual_and_bounded():
    assert ticks(0, 10, 2) == [0, 2, 4, 6, 8, 10]
    assert ticks(-.3, .3, .1) == pytest.approx([-.3, -.2, -.1, 0, .1, .2, .3])
    assert 0 < len(ticks(-1e12, 1e12, 1e-12)) <= 2000
    assert 0 < len(ticks(0, 10, 0)) < 100
    assert nice_interval(10) == 1
    assert nice_interval(37) == 5


def test_axis_validation_independent_controls():
    axis = Axis(-4, 17, .5, .1, "Price", visible=False, ticks=False, numbers=True,
                arrowheads="both", position=3, number_format="pi")
    rebuilt = Axis.from_dict(axis.__dict__)
    assert rebuilt == axis
    for changes in ({"minimum": 20}, {"major": -1}, {"maximum": math.nan}, {"arrowheads": "wrong"}):
        with pytest.raises(ValueError):
            Axis.from_dict({**axis.__dict__, **changes})


def test_arrow_points_in_drag_direction():
    for end in [(10, 0), (0, -10), (-10, 5), (0, 10)]:
        polygon = arrow_polygon((0, 0), end, 2)
        assert polygon[0] == end
        base = ((polygon[1][0]+polygon[2][0])/2, (polygon[1][1]+polygon[2][1])/2)
        assert end[0]*(end[0]-base[0])+end[1]*(end[1]-base[1]) > 0
        assert math.dist(end, base) == pytest.approx(2)
    assert arrow_polygon((1, 1), (1, 1)) == []


def test_curve_interpolates_knots_and_changes_with_handle():
    knots = [[0, 0], [2, 4], [7, 2], [10, 0]]
    sampled = smooth_curve(knots, steps=12)
    assert sampled[0] == (0, 0) and sampled[-1] == (10, 0)
    assert sampled[12] == (2, 4) and sampled[24] == (7, 2)
    knots[1][1] = 7
    edited = smooth_curve(knots, steps=12)
    assert edited[12] == (2, 7) and edited[4] != sampled[4]


def test_infinite_and_finite_line_clipping():
    assert clip_line((3, 3), (4, 4), (0, 10, 0, 10), infinite=True) == ((0, 0), (10, 10))
    assert clip_line((-3, 5), (4, 5), (0, 10, 0, 10)) == ((0, 5), (4, 5))
    assert clip_line((-3, 15), (4, 15), (0, 10, 0, 10)) is None
    assert segment_intersection((0, 0), (10, 10), (0, 10), (10, 0)) == (5, 5)


def test_pi_and_decimal_tick_formatting():
    assert format_number(math.pi/2, "pi") == "π/2"
    assert format_number(-math.pi, "pi") == "−π"
    assert format_number(2.345, "decimal", 2) == "2.35"


def rich_document():
    doc = make_template("Supply and demand")
    doc.objects.extend([
        GraphObject("function", name="Mathematical demand", label="D₂",
                    data={"expression": "y=8-0.5x", "domain_min": 1, "domain_max": 9, "offset_x": 2, "label_position": [8, 6]}),
        GraphObject("scatter", name="Observations", data={"rows": [[1, 3], [2, 5], [3, 7]]}),
        GraphObject("arrow", [[1, 2], [4, 5]], name="Shift", visible=False, locked=True, group="Market",
                    style={"color": "#aabbcc", "line_style": "dash-dot", "width": 3, "arrow_start": True}),
        GraphObject("infinite_line", [[1, 1], [2, 3]], name="Infinite line")])
    doc.type_visibility = {"construction": False}
    return doc


def test_document_roundtrip_preserves_geometry_names_styles_expressions_and_data(tmp_path):
    doc = rich_document()
    doc.save(tmp_path / "market.graphite")
    loaded = Document.load(tmp_path / "market.graphite")
    assert loaded.to_dict() == doc.to_dict()
    assert not list(tmp_path.glob("*.tmp"))
    loaded.objects[0].points[0][0] = 100
    assert doc.objects[0].points[0][0] != 100


@pytest.mark.parametrize("corrupt", ["version", "format", "nan", "duplicates", "geometry", "bool", "style", "fields"])
def test_corrupt_documents_rejected(corrupt):
    raw = rich_document().to_dict()
    if corrupt == "version": raw["version"] = 999
    if corrupt == "format": raw["format"] = "foreign-format"
    if corrupt == "nan": raw["x_axis"]["minimum"] = math.nan
    if corrupt == "duplicates": raw["objects"].append(copy.deepcopy(raw["objects"][0]))
    if corrupt == "geometry": raw["objects"][0]["points"] = [[1]]
    if corrupt == "bool": raw["objects"][0]["visible"] = "yes"
    if corrupt == "style": raw["objects"][0]["style"]["width"] = -2
    if corrupt == "fields": raw["unrecognized"] = True
    with pytest.raises(ValueError):
        Document.from_dict(raw)


def test_history_transactions_undo_redo_and_saved_state():
    doc = Document()
    history = History(doc)
    before = doc.to_dict()
    doc.objects.append(GraphObject("point", [[4, 7]], name="A", label="A"))
    assert history.commit(before, "Place point")
    assert history.can_undo and history.is_dirty()
    history.mark_saved()
    assert not history.is_dirty()
    before = doc.to_dict()
    doc.objects[0].visible = False
    doc.objects[0].points[0] = [5, 8]
    doc.x_axis.arrowheads = "both"
    history.commit(before, "Edit point and axes")
    undone = history.undo()
    assert undone.objects[0].points == [[4, 7]]
    assert undone.objects[0].visible
    assert not history.is_dirty()
    assert history.undo_label == "Place point"
    redone = history.redo()
    assert not redone.objects[0].visible
    assert redone.objects[0].points == [[5, 8]]
    assert history.is_dirty()
    history.undo()
    before = history.document.to_dict()
    history.document.title = "Different branch"
    history.commit(before)
    assert not history.can_redo


def test_every_template_is_a_valid_editable_document():
    for name in template_names():
        doc = make_template(name)
        doc.validate()
        assert Document.from_dict(doc.to_dict()).to_dict() == doc.to_dict()
        assert all(not obj.locked for obj in doc.objects)


def test_positive_coordinate_documents_disable_negative_axis_directions():
    docs = [Document()] + [make_template(name) for name in template_names() if name != "Cartesian"]
    for doc in docs:
        assert doc.mode == "positive"
        assert doc.x_axis.positive and not doc.x_axis.negative
        assert doc.y_axis.positive and not doc.y_axis.negative
    cartesian = make_template("Cartesian")
    assert cartesian.x_axis.negative and cartesian.y_axis.negative


def test_invalid_file_leaves_original_contents(tmp_path):
    path = tmp_path / "existing.graphite"
    doc = Document()
    doc.save(path)
    original = path.read_bytes()
    doc.x_axis.maximum = doc.x_axis.minimum
    with pytest.raises(ValueError):
        doc.save(path)
    assert path.read_bytes() == original
