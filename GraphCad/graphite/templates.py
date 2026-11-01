"""Unrestricted example documents; every template element is editable."""
from __future__ import annotations
from .model import Axis, Document, GraphObject

TEMPLATES = ["Economics", "Cartesian", "Supply and demand", "AD–AS", "Production possibility",
             "Cost and revenue", "Blank coordinates", "Blank canvas"]


def template_names() -> list[str]:
    return list(TEMPLATES)


def _object(kind, points, name, label="", color="#2459ad", **data):
    return GraphObject(kind=kind, points=points, name=name, label=label,
                       style={"color": color, "width": 2.2, "fill": color}, data=data)


def _construction(point):
    x, y = point
    style = {"color": "#758399", "line_style": "dashed", "width": 1.2}
    return [GraphObject("construction", [[x, 0], [x, y]], name="Quantity guide", style=style),
            GraphObject("construction", [[0, y], [x, y]], name="Price guide", style=style)]


def make_template(name: str) -> Document:
    aliases = {"Positive quadrant": "Economics", "Four quadrants": "Cartesian", "AD-AS": "AD–AS",
               "Production possibility curve": "Production possibility", "Supply & demand": "Supply and demand"}
    name = aliases.get(name, name)
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name}")
    doc = Document(title=name, grid_major=False, origin_visible=False)
    doc.x_axis = Axis(title="Quantity", numbers=False, ticks=False, negative=False)
    doc.y_axis = Axis(title="Price", numbers=False, ticks=False, label_side="left", negative=False)
    if name == "Cartesian":
        doc.mode = "four-quadrant"
        doc.x_axis = Axis(-10, 10, 2, .5, "x", arrowheads="both")
        doc.y_axis = Axis(-10, 10, 2, .5, "y", arrowheads="both", label_side="left")
        doc.grid_major = True
        doc.origin_visible = True
    elif name == "Blank coordinates":
        doc.x_axis.title, doc.y_axis.title = "x", "y"
        doc.grid_major = True
        doc.x_axis.ticks = doc.y_axis.ticks = True
        doc.x_axis.numbers = doc.y_axis.numbers = True
    elif name == "Blank canvas":
        doc.x_axis.visible = doc.y_axis.visible = False
        doc.origin_label = False
    elif name in {"Supply and demand", "AD–AS"}:
        if name == "AD–AS":
            doc.x_axis.title, doc.y_axis.title = "Real GDP", "Price level"
            down, up = "AD", "SRAS"
        else:
            down, up = "D", "S"
        doc.objects = _construction((5, 5)) + [
            _object("line", [[1.2, 8.8], [8.8, 1.2]], "Demand curve", down, "#2459ad", label_position=[8.9, 1.3]),
            _object("line", [[1.2, 1.2], [8.8, 8.8]], "Supply curve", up, "#b45c2c", label_position=[8.9, 8.9]),
            _object("point", [[5, 5]], "Equilibrium", "E", "#182c49", label_position=[5.25, 5.3]),
            _object("text", [[4.7, -.45]], "Equilibrium quantity label", "", "#33465f", text="Qₑ"),
            _object("text", [[-.30, 5.05]], "Equilibrium price label", "", "#33465f", text="Pₑ")]
    elif name == "Production possibility":
        doc.x_axis.title, doc.y_axis.title = "Capital goods", "Consumer goods"
        doc.objects = [_object("curve", [[0, 9], [3, 8.7], [6, 6.8], [8.2, 4], [9, 0]], "Production possibility frontier", "PPC", label_position=[7.7, 6]),
                       _object("point", [[6, 6.8]], "Efficient allocation", "A", "#182c49", label_position=[6.1, 7.15]),
                       _object("point", [[3, 3]], "Underutilized resources", "B", "#b45c2c", label_position=[3.2, 3.2])]
    elif name == "Cost and revenue":
        doc.y_axis.title = "Costs and revenue"
        doc.objects = [_object("curve", [[1, 8.5], [2.4, 4.3], [4.8, 3.5], [7, 4.5], [9, 7]], "Average cost", "AC", "#2459ad", label_position=[9.1, 7.1]),
                       _object("curve", [[1, 5.7], [2.6, 2.1], [4.5, 2.5], [6.4, 5.4], [8, 9]], "Marginal cost", "MC", "#b45c2c", label_position=[8.1, 9.05]),
                       _object("line", [[.6, 8.3], [8.9, 1.4]], "Average revenue", "AR", "#45816d", label_position=[9, 1.5]),
                       _object("line", [[.6, 8.3], [5.7, 0]], "Marginal revenue", "MR", "#7a659f", label_position=[5.8, .3])]
    doc.validate()
    return doc
