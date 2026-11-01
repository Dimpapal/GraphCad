"""Coordinate transforms and vector geometry, independent of Qt."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Sequence

Point = tuple[float, float]


def _finite_point(value: Sequence[float], name: str = "Point") -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} needs two finite coordinates")
    if any(isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) for coordinate in value):
        raise ValueError(f"{name} needs two finite coordinates")
    result = float(value[0]), float(value[1])
    if not all(math.isfinite(coordinate) for coordinate in result):
        raise ValueError(f"{name} needs two finite coordinates")
    return result


def project_point_to_line(point: Sequence[float], a: Sequence[float], b: Sequence[float],
                          clamp: bool = False) -> Point:
    """Orthogonal projection in document units, optionally onto a finite segment.

    With ``clamp=False`` the supporting line is used even beyond either endpoint.
    A coincident endpoint pair cannot define a direction and raises ValueError.
    No viewport, scale, or screen-axis convention participates in the calculation.
    """
    point, a, b = _finite_point(point), _finite_point(a, "Line start"), _finite_point(b, "Line end")
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length == 0:
        raise ValueError("A projection target needs two different finite endpoints")
    ux, uy = dx / length, dy / length
    distance = (point[0] - a[0]) * ux + (point[1] - a[1]) * uy
    if clamp:
        if distance <= 0:
            return a
        if distance >= length:
            return b
    # Preserve an already collinear point exactly, including a zero-length
    # perpendicular connector, rather than introduce unit-vector roundoff.
    first_term, second_term = (point[0] - a[0]) * uy, (point[1] - a[1]) * ux
    perpendicular = first_term - second_term
    tolerance = 8 * math.ulp(max(abs(first_term), abs(second_term)))
    if abs(perpendicular) <= tolerance:
        return point
    result = a[0] + distance * ux, a[1] + distance * uy
    if not all(math.isfinite(coordinate) for coordinate in result):
        raise ValueError("Projection lies outside the finite coordinate range")
    return result


def line_geometry(obj) -> tuple[Point, Point, bool] | None:
    """Return the object's document-space straight geometry, or None.

    ``line``/``segment``, ``construction``, and ``arrow`` use finite endpoints.
    Horizontal/vertical objects apply the same endpoint constraint as the renderer.
    ``infinite_line`` uses its supporting line. Polylines deliberately return None;
    callers can project onto each finite edge separately.
    """
    kind = obj.get("kind") if isinstance(obj, dict) else getattr(obj, "kind", None)
    if kind not in ("line", "segment", "construction", "arrow", "horizontal", "vertical", "infinite_line"):
        return None
    points = obj.get("points") if isinstance(obj, dict) else getattr(obj, "points", None)
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return None
    a, b = _finite_point(points[0], "Line start"), _finite_point(points[1], "Line end")
    if kind == "horizontal":
        b = b[0], a[1]
    elif kind == "vertical":
        b = a[0], b[1]
    return a, b, kind == "infinite_line"


def _reference_direction(reference) -> Point:
    geometry = line_geometry(reference)
    if geometry is not None:
        a, b, _ = geometry
        direction = b[0] - a[0], b[1] - a[1]
    elif isinstance(reference, (list, tuple)) and len(reference) == 2:
        if all(isinstance(value, (list, tuple)) for value in reference):
            a, b = _finite_point(reference[0]), _finite_point(reference[1])
            direction = b[0] - a[0], b[1] - a[1]
        else:
            direction = _finite_point(reference, "Reference direction")
    else:
        raise ValueError("Choose a straight reference line for this constraint")
    length = math.hypot(*direction)
    if not math.isfinite(length) or length == 0:
        raise ValueError("The reference line must have different endpoints")
    return direction[0] / length, direction[1] / length


def _unit_angle(degrees: float) -> Point:
    degrees %= 360
    if degrees % 90 == 0:
        return ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[int(degrees / 90)]
    radians = math.radians(degrees)
    return math.cos(radians), math.sin(radians)


def constrain_endpoint(start: Sequence[float], end: Sequence[float], mode: str = "free",
                       angle_degrees: float = 0, increment_degrees: float = 45,
                       reference=None) -> Point:
    """Constrain an endpoint using graph-space angles, never screen slopes.

    Fixed directions (horizontal, vertical, parallel, perpendicular, angle) project
    the pointer onto the supporting line through start. ``angular`` snaps its angle
    to the nearest increment while retaining the pointer's radial distance.
    Reference may be a straight GraphObject, endpoint pair, or direction vector.
    """
    start, end = _finite_point(start, "Start"), _finite_point(end, "End")
    if not isinstance(mode, str):
        raise ValueError("Constraint mode must be text")
    mode = mode.strip().lower().replace("-", "_").replace(" ", "_")
    mode = {"none": "free", "h": "horizontal", "v": "vertical", "fixed": "angle",
            "fixed_angle": "angle", "snap": "angular", "angular_snap": "angular",
            "angle_snap": "angular", "angular_snapping": "angular"}.get(mode, mode)
    if mode == "free":
        return end
    if mode == "horizontal":
        return end[0], start[1]
    if mode == "vertical":
        return start[0], end[1]
    if mode in ("parallel", "perpendicular"):
        ux, uy = _reference_direction(reference)
        if mode == "perpendicular":
            ux, uy = -uy, ux
    elif mode == "angle":
        if isinstance(angle_degrees, bool) or not isinstance(angle_degrees, (float, int)) or not math.isfinite(angle_degrees):
            raise ValueError("Angle must be a finite number of degrees")
        ux, uy = _unit_angle(angle_degrees)
    elif mode == "angular":
        if isinstance(increment_degrees, bool) or not isinstance(increment_degrees, (float, int)) or not math.isfinite(increment_degrees) or not 0 < increment_degrees <= 360:
            raise ValueError("Angular increment must be greater than 0 and at most 360 degrees")
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return start
        theta = math.degrees(math.atan2(dy, dx))
        snapped = math.floor(theta / increment_degrees + .5) * increment_degrees
        ux, uy = _unit_angle(snapped)
        return start[0] + length * ux, start[1] + length * uy
    else:
        raise ValueError(f"Unknown constraint mode: {mode}")
    distance = (end[0] - start[0]) * ux + (end[1] - start[1]) * uy
    return start[0] + distance * ux, start[1] + distance * uy


@dataclass
class ViewTransform:
    bounds: tuple[float, float, float, float]
    rect: tuple[float, float, float, float]

    def __post_init__(self):
        if len(self.bounds) != 4 or len(self.rect) != 4 or not all(math.isfinite(v) for v in (*self.bounds, *self.rect)):
            raise ValueError("Transform needs finite bounds and rectangle")
        xmin, xmax, ymin, ymax = self.bounds
        _, _, w, h = self.rect
        if xmax <= xmin or ymax <= ymin or w <= 0 or h <= 0:
            raise ValueError("Transform ranges and dimensions must be positive")

    @property
    def sx(self):
        return self.rect[2] / (self.bounds[1] - self.bounds[0])

    @property
    def sy(self):
        return self.rect[3] / (self.bounds[3] - self.bounds[2])

    def forward(self, point: Sequence[float]) -> Point:
        x, y = point
        return self.rect[0] + (x - self.bounds[0]) * self.sx, self.rect[1] + (self.bounds[3] - y) * self.sy

    def inverse(self, point: Sequence[float]) -> Point:
        x, y = point
        return self.bounds[0] + (x - self.rect[0]) / self.sx, self.bounds[3] - (y - self.rect[1]) / self.sy


def nice_interval(span: float, target: int = 10) -> float:
    if not math.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(1, target)
    exponent = 10 ** math.floor(math.log10(raw))
    fraction = raw / exponent
    nice = next((n for n in (1, 2, 2.5, 5, 10) if n >= fraction), 10)
    return nice * exponent


def ticks(minimum: float, maximum: float, interval: float, limit: int = 2000) -> list[float]:
    if not all(math.isfinite(v) for v in (minimum, maximum, interval)) or maximum <= minimum:
        return []
    if interval <= 0:
        interval = nice_interval(maximum - minimum)
    first = math.ceil(minimum / interval - 1e-10)
    last = math.floor(maximum / interval + 1e-10)
    count = last - first + 1
    if count <= 0:
        return []
    stride = max(1, math.ceil(count / limit))
    return [0.0 if abs(i * interval) < interval * 1e-10 else i * interval for i in range(first, last + 1, stride)]


def smooth_curve(points: Sequence[Sequence[float]], steps: int = 16) -> list[Point]:
    """Interpolating Catmull-Rom spline, with exact endpoints and editable knots."""
    pts = [tuple(p) for p in points]
    if len(pts) < 3:
        return pts
    result = []
    steps = max(2, min(128, steps))
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        for j in range(steps):
            t = j / steps
            coords = []
            for axis in (0, 1):
                a, b, c, d = p0[axis], p1[axis], p2[axis], p3[axis]
                coords.append(.5 * ((2 * b) + (-a + c) * t + (2*a - 5*b + 4*c - d)*t*t + (-a + 3*b - 3*c + d)*t*t*t))
            result.append(tuple(coords))
    result.append(pts[-1])
    return result


def arrow_polygon(start: Sequence[float], end: Sequence[float], size: float = 12) -> list[Point]:
    """Filled triangular head in input coordinates, pointing from start to end."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-15:
        return []
    size = min(size, length)
    ux, uy = dx / length, dy / length
    base = end[0] - ux * size, end[1] - uy * size
    return [tuple(end), (base[0] - uy * size * .45, base[1] + ux * size * .45),
            (base[0] + uy * size * .45, base[1] - ux * size * .45)]


def clip_line(start: Sequence[float], end: Sequence[float], bounds: Sequence[float], infinite: bool = False) -> tuple[Point, Point] | None:
    """Liang-Barsky clip; also supports an infinite line through the two points."""
    xmin, xmax, ymin, ymax = bounds
    x, y = start
    dx, dy = end[0] - x, end[1] - y
    if abs(dx) < 1e-30 and abs(dy) < 1e-30:
        return (tuple(start), tuple(end)) if xmin <= x <= xmax and ymin <= y <= ymax else None
    lo, hi = (-math.inf, math.inf) if infinite else (0.0, 1.0)
    for p, q in ((-dx, x-xmin), (dx, xmax-x), (-dy, y-ymin), (dy, ymax-y)):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            lo = max(lo, q/p)
        else:
            hi = min(hi, q/p)
        if lo > hi:
            return None
    return ((x + lo*dx, y + lo*dy), (x + hi*dx, y + hi*dy))


def segment_intersection(a, b, c, d, tolerance: float = 1e-10) -> Point | None:
    dx, dy, ex, ey = b[0]-a[0], b[1]-a[1], d[0]-c[0], d[1]-c[1]
    determinant = dx * ey - dy * ex
    if abs(determinant) <= tolerance:
        return None
    cx, cy = c[0]-a[0], c[1]-a[1]
    t = (cx * ey - cy * ex) / determinant
    u = (cx * dy - cy * dx) / determinant
    if -tolerance <= t <= 1+tolerance and -tolerance <= u <= 1+tolerance:
        return a[0] + t*dx, a[1] + t*dy
    return None


def format_number(value: float, mode: str = "auto", decimals: int = 2) -> str:
    if abs(value) < 1e-12:
        return "0"
    if mode == "scientific":
        return f"{value:.{decimals}e}"
    if mode == "decimal":
        return f"{value:.{decimals}f}"
    if mode == "pi":
        from fractions import Fraction
        ratio = Fraction(value / math.pi).limit_denominator(24)
        if abs(float(ratio) * math.pi - value) < 1e-7:
            n, d = ratio.numerator, ratio.denominator
            top = ("−" if n < 0 else "") + ("" if abs(n) == 1 else str(abs(n))) + "π"
            return top if d == 1 else f"{top}/{d}"
    return f"{value:.6g}"
