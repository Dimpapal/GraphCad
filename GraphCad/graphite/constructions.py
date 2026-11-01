"""Persistent perpendicular dependencies with ordinary, materialized vector objects.

Linked helpers are locked against direct coordinate edits. Their styles, names,
labels, and visibility stay independently editable. When a dependency is deleted,
the helper freezes at its last coordinates, detaches, and unlocks. Degenerate
targets retain their last valid construction until the target has a direction
again. Cycles and malformed metadata are rejected before any geometry changes.
"""
from __future__ import annotations

from collections import deque
import uuid

from .geometry import line_geometry, project_point_to_line
from .model import GraphObject


def perpendicular_metadata(obj) -> dict | None:
    """Validate the reserved metadata namespace; unrelated data is untouched."""
    if "perpendicular" not in obj.data:
        return None
    metadata = obj.data["perpendicular"]
    if not isinstance(metadata, dict) or set(metadata) - {"role", "source_id", "target_id", "axis"}:
        raise ValueError("Perpendicular construction metadata is invalid")
    role = metadata.get("role")
    if role not in ("foot", "segment"):
        raise ValueError("Perpendicular construction role must be foot or segment")
    if obj.kind != ("point" if role == "foot" else "construction"):
        raise ValueError("Perpendicular metadata does not match its object type")
    source_id = metadata.get("source_id")
    if not isinstance(source_id, str) or not source_id or len(source_id) > 1000:
        raise ValueError("Perpendicular source must be a point identifier")
    if ("target_id" in metadata) == ("axis" in metadata):
        raise ValueError("Choose exactly one perpendicular target: a straight object or an axis")
    if "target_id" in metadata:
        target_id = metadata["target_id"]
        if not isinstance(target_id, str) or not target_id or len(target_id) > 1000:
            raise ValueError("Perpendicular target must be a straight object identifier")
    elif metadata["axis"] not in ("x", "y"):
        raise ValueError("Perpendicular axis must be x or y")
    return metadata


def _target_geometry(document, metadata, by_id, planned):
    if "axis" in metadata:
        if metadata["axis"] == "x":
            position = document.x_axis.position
            return (0.0, position), (1.0, position)
        position = document.y_axis.position
        return (position, 0.0), (position, 1.0)
    target = by_id[metadata["target_id"]]
    points = planned.get(target.id, target.points)
    geometry = line_geometry({"kind": target.kind, "points": points})
    if geometry is None:
        raise ValueError("Perpendicular target must be a straight line, segment, or arrow")
    return geometry[0], geometry[1]


def create_perpendicular(document, source_id: str, target_id: str | None = None,
                         axis: str | None = None) -> list[GraphObject]:
    """Create, but do not append, a linked foot point and perpendicular segment.

    Projection uses the supporting line even for a finite target. This preserves
    a right angle when the foot falls beyond the target segment's endpoints.
    A source already on the line produces a valid, zero-length connector.
    """
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("Choose a source point")
    if (target_id is None) == (axis is None):
        raise ValueError("Choose one straight target object or the x/y axis")
    if axis is not None and axis not in ("x", "y"):
        raise ValueError("Choose the x or y axis")
    if target_id is not None and (not isinstance(target_id, str) or not target_id):
        raise ValueError("Choose a straight target object")
    document.update_constructions()
    by_id = {obj.id: obj for obj in document.objects}
    source = by_id.get(source_id)
    if source is None or source.kind != "point" or not source.points:
        raise ValueError("Perpendicular source must be an existing point")
    if target_id is not None and target_id not in by_id:
        raise ValueError("Perpendicular target does not exist")
    target = {"axis": axis} if axis is not None else {"target_id": target_id}
    metadata = {"source_id": source_id, **target}
    a, b = _target_geometry(document, metadata, by_id, {})
    foot = project_point_to_line(source.points[0], a, b)
    if max(abs(coordinate) for coordinate in foot) > 1e12:
        raise ValueError("Perpendicular foot lies outside the supported coordinate range")
    group = str(uuid.uuid4())
    source_name = source.name or "Point"
    foot_obj = GraphObject("point", points=[list(foot)], name=document.unique_name(source_name + " perpendicular foot"),
                           group=group, locked=True, style={"color": "#2459ad", "fill": "#ffffff", "marker_size": 4},
                           data={"perpendicular": {"role": "foot", **metadata}})
    segment_obj = GraphObject("construction", points=[list(source.points[0]), list(foot)],
                              name=document.unique_name(source_name + " perpendicular"), group=group, locked=True,
                              style={"color": "#7b8993", "line_style": "dashed", "width": 1.3},
                              data={"perpendicular": {"role": "segment", **metadata}})
    foot_obj.validate()
    segment_obj.validate()
    return [foot_obj, segment_obj]


def _construction_order(document):
    """Preflight references and compute an iterative dependency ordering."""
    by_id = {}
    derived = {}
    for obj in document.objects:
        if obj.id in by_id:
            raise ValueError("Duplicate object identifier")
        by_id[obj.id] = obj
        metadata = perpendicular_metadata(obj)
        if metadata is not None:
            derived[obj.id] = metadata
    if not derived:
        return by_id, derived, []
    dependencies, followers = {}, {identifier: [] for identifier in derived}
    for identifier, metadata in derived.items():
        source = by_id.get(metadata["source_id"])
        if source is not None and (source.kind != "point" or not source.points):
            raise ValueError("Perpendicular source must be an existing point")
        target_id = metadata.get("target_id")
        target = by_id.get(target_id) if target_id else None
        if target is not None and line_geometry(target) is None:
            raise ValueError("Perpendicular target must be a straight line, segment, or arrow")
        refs = {metadata["source_id"]}
        if target_id is not None:
            refs.add(target_id)
        deps = refs & derived.keys()
        dependencies[identifier] = len(deps)
        for dep in deps:
            followers[dep].append(identifier)
    queue = deque(identifier for identifier in derived if dependencies[identifier] == 0)
    ordered = []
    while queue:
        identifier = queue.popleft()
        ordered.append(identifier)
        for child in followers[identifier]:
            dependencies[child] -= 1
            if dependencies[child] == 0:
                queue.append(child)
    if len(ordered) != len(derived):
        raise ValueError("Perpendicular constructions cannot contain dependency cycles")
    return by_id, derived, ordered


def validate_constructions(document) -> None:
    """Validate the dependency graph without changing geometry or metadata."""
    _construction_order(document)


def resolve_constructions(document) -> list[str]:
    """Update dependencies in a bounded topological pass and return any notices.

    All metadata, reference types, and cycles are checked before applying changes.
    The algorithm is iterative, O(number of objects + dependency edges), and does
    not recurse even when construction chains are long.
    """
    by_id, derived, ordered = _construction_order(document)
    planned, detached, notices = {}, set(), []
    for identifier in ordered:
        obj, metadata = by_id[identifier], derived[identifier]
        source = by_id.get(metadata["source_id"])
        target_missing = "target_id" in metadata and metadata["target_id"] not in by_id
        if source is None or target_missing:
            detached.add(identifier)
            notices.append(f"{obj.name or obj.kind}: deleted dependency; geometry frozen and detached")
            continue
        source_point = planned.get(source.id, source.points)[0]
        a, b = _target_geometry(document, metadata, by_id, planned)
        try:
            foot = project_point_to_line(source_point, a, b)
        except ValueError:
            notices.append(f"{obj.name or obj.kind}: target has no direction; retaining last valid geometry")
            continue
        if max(abs(coordinate) for coordinate in foot) > 1e12:
            notices.append(f"{obj.name or obj.kind}: foot outside supported range; retaining last valid geometry")
            continue
        planned[identifier] = [list(foot)] if metadata["role"] == "foot" else [list(source_point), list(foot)]
    for identifier in ordered:
        obj = by_id[identifier]
        if identifier in detached:
            obj.data.pop("perpendicular", None)
            obj.locked = False
        else:
            obj.locked = True
            if identifier in planned:
                obj.points = planned[identifier]
    return notices
