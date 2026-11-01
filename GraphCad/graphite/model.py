"""Versioned, UI-independent document model and atomic JSON persistence."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
import uuid

FORMAT = "graphite-document"
VERSION = 1
MAX_OBJECTS = 20000
MAX_POINTS = 200000
KINDS = {"point", "line", "segment", "infinite_line", "horizontal", "vertical", "polyline", "curve", "arrow", "text", "function", "scatter", "regression", "construction"}
LINE_STYLES = {"solid", "dashed", "dotted", "dash-dot"}


def _number(value: Any, name: str, low: float = -1e12, high: float = 1e12) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low:g} and {high:g}")
    return value


def _text(value: Any, name: str, limit: int = 10000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{name} must be text of at most {limit} characters")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def _json_value(value: Any, depth: int = 0) -> None:
    if depth > 12:
        raise ValueError("Nested document data is too deep")
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str) and len(value) > 100000:
            raise ValueError("Text value is too large")
        return
    if isinstance(value, (float, int)):
        _number(value, "Data value")
    elif isinstance(value, list):
        if len(value) > MAX_POINTS:
            raise ValueError("Too many data values")
        for item in value:
            _json_value(item, depth + 1)
    elif isinstance(value, dict):
        if len(value) > 10000:
            raise ValueError("Too many data fields")
        for key, item in value.items():
            _text(key, "Data key", 256)
            _json_value(item, depth + 1)
    else:
        raise ValueError("Document contains an unsupported data value")


def _points(value: Any, name: str = "Points") -> list[list[float]]:
    if not isinstance(value, list) or len(value) > MAX_POINTS:
        raise ValueError(f"{name} must be a bounded list of coordinate pairs")
    result = []
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"Each {name.lower()} entry must contain X and Y")
        result.append([_number(pair[0], "X"), _number(pair[1], "Y")])
    return result


@dataclass
class Axis:
    minimum: float = 0.0
    maximum: float = 10.0
    major: float = 1.0
    minor: float = 0.2
    title: str = ""
    visible: bool = True
    positive: bool = True
    negative: bool = True
    ticks: bool = True
    numbers: bool = True
    title_visible: bool = True
    arrowheads: str = "positive"
    position: float = 0.0
    label_side: str = "below"
    number_format: str = "auto"
    decimals: int = 2
    width: float = 1.5
    line_style: str = "solid"

    def validate(self) -> None:
        self.minimum = _number(self.minimum, "Axis minimum")
        self.maximum = _number(self.maximum, "Axis maximum")
        if self.maximum <= self.minimum or self.maximum - self.minimum < 1e-10:
            raise ValueError("Axis maximum must be greater than minimum (range at least 1e-10)")
        self.major = _number(self.major, "Major interval", 0, 1e12)
        self.minor = _number(self.minor, "Minor interval", 0, 1e12)
        self.position = _number(self.position, "Axis position")
        self.width = _number(self.width, "Axis thickness", 0.1, 30)
        self.title = _text(self.title, "Axis title", 1000)
        for attr in ("visible", "positive", "negative", "ticks", "numbers", "title_visible"):
            _bool(getattr(self, attr), attr)
        if not isinstance(self.arrowheads, str) or self.arrowheads not in {"none", "positive", "negative", "both"}:
            raise ValueError("Invalid axis arrowhead mode")
        if not isinstance(self.line_style, str) or self.line_style not in LINE_STYLES:
            raise ValueError("Invalid axis line style")
        if not isinstance(self.number_format, str) or self.number_format not in {"auto", "decimal", "scientific", "pi"}:
            raise ValueError("Invalid numeric format")
        if not isinstance(self.label_side, str) or self.label_side not in {"below", "above", "left", "right"}:
            raise ValueError("Invalid axis label placement")
        if isinstance(self.decimals, bool) or not isinstance(self.decimals, int) or not 0 <= self.decimals <= 12:
            raise ValueError("Decimal places must be between 0 and 12")

    @classmethod
    def from_dict(cls, raw: dict) -> Axis:
        if not isinstance(raw, dict):
            raise ValueError("Axis settings must be an object")
        known = {f.name for f in fields(cls)}
        if set(raw) - known:
            raise ValueError("Unrecognized axis settings")
        result = cls(**raw)
        result.validate()
        return result


def default_style() -> dict:
    return {"color": "#2459ad", "width": 2.0, "line_style": "solid", "opacity": 1.0,
            "marker": "circle", "marker_size": 6.0, "fill": "#ffffff", "font": "Sans Serif",
            "font_size": 12.0, "bold": False, "italic": False, "align": "left", "rotation": 0.0,
            "arrow_start": False, "arrow_end": True, "arrow_size": 12.0, "background": "transparent"}


@dataclass
class GraphObject:
    kind: str
    points: list[list[float]] = field(default_factory=list)
    name: str = ""
    label: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    visible: bool = True
    locked: bool = False
    group: str = ""
    layer: str = "Drawing"
    style: dict = field(default_factory=default_style)
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.style = {**default_style(), **self.style}

    def validate(self) -> None:
        if not isinstance(self.kind, str) or self.kind not in KINDS:
            raise ValueError(f"Unknown object kind: {self.kind!r}")
        self.points = _points(self.points)
        minimum = {"point": 1, "text": 1, "segment": 2, "line": 2, "infinite_line": 2, "horizontal": 2,
                   "vertical": 2, "arrow": 2, "construction": 2, "polyline": 2, "curve": 2}.get(self.kind, 0)
        if len(self.points) < minimum:
            raise ValueError(f"A {self.kind} object needs at least {minimum} coordinate(s)")
        for attr in ("name", "label", "group", "layer", "id"):
            _text(getattr(self, attr), attr, 10000 if attr == "label" else 1000)
        if not self.id:
            raise ValueError("Object identifier cannot be empty")
        _bool(self.visible, "Visibility")
        _bool(self.locked, "Lock state")
        if not isinstance(self.style, dict) or not isinstance(self.data, dict):
            raise ValueError("Object style and data must be objects")
        _json_value(self.style)
        _json_value(self.data)
        for key, low, high in (("width", .1, 50), ("opacity", 0, 1), ("marker_size", 1, 100),
                               ("font_size", 1, 300), ("rotation", -36000, 36000), ("arrow_size", 1, 150)):
            _number(self.style[key], key, low, high)
        if not isinstance(self.style["line_style"], str) or self.style["line_style"] not in LINE_STYLES:
            raise ValueError("Invalid object line style")
        if not isinstance(self.style["marker"], str) or self.style["marker"] not in {"circle", "square", "diamond", "cross", "triangle"}:
            raise ValueError("Invalid point marker")
        if not isinstance(self.style["align"], str) or self.style["align"] not in {"left", "center", "right"}:
            raise ValueError("Invalid text alignment")
        for key in ("bold", "italic", "arrow_start", "arrow_end"):
            _bool(self.style[key], key)
        for key in ("color", "fill", "background", "font"):
            _text(self.style[key], key, 200)
        if self.kind in {"function", "regression"} and "expression" in self.data:
            _text(self.data["expression"], "Expression", 2000)
        for key in ("offset_x", "offset_y"):
            if key in self.data:
                _number(self.data[key], key)
        if "label_position" in self.data:
            self.data["label_position"] = _points([self.data["label_position"]], "Label position")[0]
        if "label_mode" in self.data and self.data["label_mode"] not in ("name", "coordinates", "both"):
            raise ValueError("Invalid point label mode")
        if "text" in self.data:
            _text(self.data["text"], "Text content", 10000)
        if "source_id" in self.data:
            _text(self.data["source_id"], "Dataset identifier", 1000)
        if "point_labels" in self.data:
            _bool(self.data["point_labels"], "Point labels")
        if "label_visible" in self.data:
            _bool(self.data["label_visible"], "Label visibility")
        for key in ("domain_min", "domain_max"):
            if self.data.get(key) is not None:
                _number(self.data[key], key)
        if self.data.get("domain_min") is not None and self.data.get("domain_max") is not None:
            if self.data["domain_min"] >= self.data["domain_max"]:
                raise ValueError("Function domain minimum must be below its maximum")
        if self.kind == "scatter":
            if "rows" in self.data:
                self.data["rows"] = _points(self.data["rows"], "Dataset rows")
            elif not self.points:
                self.data["rows"] = []
        if "perpendicular" in self.data:
            from .constructions import perpendicular_metadata
            perpendicular_metadata(self)

    def to_dict(self) -> dict:
        return deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, raw: dict) -> GraphObject:
        if not isinstance(raw, dict):
            raise ValueError("Each drawing object must be an object")
        known = {f.name for f in fields(cls)}
        if set(raw) - known or "kind" not in raw:
            raise ValueError("Unrecognized or missing drawing object fields")
        try:
            result = cls(**deepcopy(raw))
        except (TypeError, KeyError) as exc:
            raise ValueError(f"Invalid drawing object: {exc}") from exc
        result.validate()
        return result


@dataclass
class Document:
    title: str = "Untitled"
    x_axis: Axis = field(default_factory=lambda: Axis(title="Quantity", negative=False))
    y_axis: Axis = field(default_factory=lambda: Axis(title="Price", label_side="left", negative=False))
    objects: list[GraphObject] = field(default_factory=list)
    grid_major: bool = True
    grid_minor: bool = False
    origin_visible: bool = True
    origin_label: bool = True
    labels_visible: bool = True
    type_visibility: dict = field(default_factory=dict)
    snap_grid: bool = False
    snap_points: bool = True
    snap_intersections: bool = False
    snap_lines: bool = False
    snap_tolerance_pixels: float = 10.0
    snap_interval: float = 0.5
    mode: str = "positive"
    radians: bool = True

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.x_axis.minimum, self.x_axis.maximum, self.y_axis.minimum, self.y_axis.maximum

    def get(self, object_id: str) -> GraphObject | None:
        return next((obj for obj in self.objects if obj.id == object_id), None)

    def unique_name(self, prefix: str) -> str:
        names = {obj.name for obj in self.objects}
        if prefix not in names:
            return prefix
        i = 2
        while f"{prefix} {i}" in names:
            i += 1
        return f"{prefix} {i}"

    def update_constructions(self) -> list[str]:
        """Materialize linked geometry; ordinary v1 documents remain unchanged."""
        from .constructions import resolve_constructions
        return resolve_constructions(self)

    def validate(self) -> None:
        _text(self.title, "Document title", 1000)
        self.x_axis.validate()
        self.y_axis.validate()
        if not isinstance(self.objects, list) or len(self.objects) > MAX_OBJECTS:
            raise ValueError(f"A document can contain at most {MAX_OBJECTS} objects")
        seen = set()
        total = 0
        for obj in self.objects:
            if not isinstance(obj, GraphObject):
                raise ValueError("Invalid object in document")
            obj.validate()
            if obj.id in seen:
                raise ValueError("Duplicate object identifier")
            seen.add(obj.id)
            total += len(obj.points) + len(obj.data.get("rows", []))
        if total > 1000000:
            raise ValueError("Document has too many coordinates")
        for attr in ("grid_major", "grid_minor", "origin_visible", "origin_label", "labels_visible",
                     "snap_grid", "snap_points", "snap_intersections", "snap_lines", "radians"):
            _bool(getattr(self, attr), attr)
        _number(self.snap_interval, "Snapping interval", 1e-10, 1e12)
        _number(self.snap_tolerance_pixels, "Snapping tolerance", 1, 50)
        if not isinstance(self.mode, str) or self.mode not in {"positive", "four-quadrant", "custom"}:
            raise ValueError("Invalid coordinate mode")
        if not isinstance(self.type_visibility, dict) or any(k not in KINDS or not isinstance(v, bool) for k, v in self.type_visibility.items()):
            raise ValueError("Invalid object visibility settings")
        if any("perpendicular" in obj.data for obj in self.objects):
            from .constructions import validate_constructions
            validate_constructions(self)

    def to_dict(self) -> dict:
        return {"format": FORMAT, "version": VERSION, **deepcopy(asdict(self))}

    @classmethod
    def from_dict(cls, raw: dict) -> Document:
        if not isinstance(raw, dict) or raw.get("format") != FORMAT:
            raise ValueError("This is not a GraphCad document")
        if isinstance(raw.get("version"), bool) or raw.get("version") != VERSION:
            raise ValueError(f"Unsupported GraphCad document version {raw.get('version')!r}")
        known = {f.name for f in fields(cls)}
        if set(raw) - known - {"format", "version"}:
            raise ValueError("Unrecognized document fields")
        values = {key: deepcopy(value) for key, value in raw.items() if key in known}
        values["x_axis"] = Axis.from_dict(values.get("x_axis", {}))
        values["y_axis"] = Axis.from_dict(values.get("y_axis", {}))
        objects = values.get("objects", [])
        if not isinstance(objects, list) or len(objects) > MAX_OBJECTS:
            raise ValueError("Invalid drawing object list")
        values["objects"] = [GraphObject.from_dict(obj) for obj in objects]
        try:
            result = cls(**values)
        except TypeError as exc:
            raise ValueError(f"Invalid document: {exc}") from exc
        result.update_constructions()
        result.validate()
        return result

    def clone(self) -> Document:
        return deepcopy(self)

    def save(self, path: str | Path) -> None:
        self.update_constructions()
        self.validate()
        destination = Path(path)
        contents = json.dumps(self.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                             prefix="." + destination.name, suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @classmethod
    def load(cls, path: str | Path) -> Document:
        source = Path(path)
        if source.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Document exceeds the 64 MB size limit")
        try:
            raw = json.loads(source.read_text(encoding="utf-8"), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"Non-finite number {v}")))
            return cls.from_dict(raw)
        except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
            raise ValueError(f"Cannot read GraphCad document: {exc}") from exc
