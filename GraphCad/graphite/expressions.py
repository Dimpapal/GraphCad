"""Bounded arithmetic parser and adaptive, discontinuity-aware function sampling.

Expressions are inspected ASTs interpreted directly. No eval, Python builtins,
attribute lookup, imports, subscripting, or arbitrary function calls are exposed.
"""
from __future__ import annotations
import ast
import math
import operator
import re
from typing import Callable

TOKEN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|\*\*|[+\-*/^(),]")
FUNCTIONS = {"sqrt", "abs", "exp", "ln", "log", "log10", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "floor", "ceil"}
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


class ExpressionError(ValueError):
    pass


def normalize_expression(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise ExpressionError("Enter a function, for example y = 2x + 3")
    if len(source) > 2000:
        raise ExpressionError("Expression is too long (maximum 2000 characters)")
    source = source.strip().replace("π", "pi").replace("−", "-").replace("×", "*").replace("÷", "/")
    if "=" in source:
        left, sep, source = source.partition("=")
        if left.strip().lower() != "y" or "=" in source:
            raise ExpressionError("Use y = expression, or enter the expression alone")
    source = source.strip()
    tokens = []
    cursor = 0
    while cursor < len(source):
        if source[cursor].isspace():
            cursor += 1
            continue
        match = TOKEN.match(source, cursor)
        if not match:
            raise ExpressionError(f"Unexpected character {source[cursor]!r} at position {cursor + 1}")
        tokens.append(match.group())
        cursor = match.end()
    if not tokens:
        raise ExpressionError("The expression after y = cannot be empty")
    if len(tokens) > 512:
        raise ExpressionError("Expression is too complex")
    known_names = FUNCTIONS | CONSTANTS.keys() | {"x"}
    for token in tokens:
        if token[0].isalpha() and token not in known_names:
            raise ExpressionError(f"Unknown symbol '{token}'. Use x, pi, e, or a supported function")
    result = []
    for i, token in enumerate(tokens):
        if i:
            previous = tokens[i-1]
            previous_end = previous == ")" or previous in {"x", *CONSTANTS} or previous[0].isdigit() or previous.startswith(".")
            token_start = token == "(" or token[0].isalnum() or token.startswith(".")
            if previous_end and token_start:
                result.append("*")
        result.append("**" if token == "^" else token)
    return "".join(result)


class Expression:
    def __init__(self, source: str, radians: bool = True):
        self.source = source
        self.radians = radians
        self.normalized = normalize_expression(source)
        try:
            self.tree = ast.parse(self.normalized, mode="eval").body
        except (SyntaxError, RecursionError) as exc:
            detail = getattr(exc, "msg", "expression is too deeply nested")
            raise ExpressionError(f"Invalid expression: {detail}") from exc
        self._check(self.tree)

    def _check(self, node: ast.AST, depth: int = 0) -> None:
        if depth > 40:
            raise ExpressionError("Expression is too deeply nested")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (float, int)):
                raise ExpressionError("Only numeric constants are allowed")
            try:
                if not math.isfinite(float(node.value)) or abs(node.value) > 1e100:
                    raise ExpressionError("Numeric constant is too large")
            except OverflowError as exc:
                raise ExpressionError("Numeric constant is too large") from exc
        elif isinstance(node, ast.Name):
            if node.id not in CONSTANTS and node.id != "x":
                raise ExpressionError(f"'{node.id}' requires parentheses, for example {node.id}(x)")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            self._check(node.left, depth+1)
            self._check(node.right, depth+1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            self._check(node.operand, depth+1)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            if len(node.args) != 1 or node.keywords:
                raise ExpressionError(f"{node.func.id} takes one argument")
            self._check(node.args[0], depth+1)
        else:
            raise ExpressionError("Use arithmetic, parentheses, x, and supported mathematical functions only")

    def _evaluate(self, node: ast.AST, x: float) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return x if node.id == "x" else CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp):
            value = self._evaluate(node.operand, x)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = self._evaluate(node.left, x), self._evaluate(node.right, x)
            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000:
                    raise ValueError("Exponent too large")
                return math.pow(left, right)
            operation = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}[type(node.op)]
            return operation(left, right)
        value = self._evaluate(node.args[0], x)
        name = node.func.id
        if name in {"sin", "cos", "tan"}:
            return getattr(math, name)(value if self.radians else math.radians(value))
        if name in {"asin", "acos", "atan"}:
            result = getattr(math, name)(value)
            return result if self.radians else math.degrees(result)
        function = {"ln": math.log, "log": math.log10, "abs": abs}.get(name)
        return (function or getattr(math, name))(value)

    def evaluate(self, x: float) -> float:
        try:
            value = self._evaluate(self.tree, float(x))
            return float(value) if math.isfinite(value) else math.nan
        except (ArithmeticError, ValueError, TypeError):
            return math.nan

    __call__ = evaluate


def sample_function(expression: str | Expression, xmin: float, xmax: float, ymin: float, ymax: float,
                    pixel_width: int = 1000, domain: tuple[float | None, float | None] | None = None,
                    radians: bool = True) -> list[list[tuple[float, float]]]:
    """Sample at subpixel curvature tolerance, splitting at poles and undefined values.

    The finite viewport supplies an error scale. Recursive refinement is bounded
    (depth 12, 100k evaluations) so pathological expressions cannot freeze the UI.
    Samples far outside the viewport are discarded instead of joining a pole.
    """
    expr = expression if isinstance(expression, Expression) else Expression(expression, radians)
    if not all(math.isfinite(v) for v in (xmin, xmax, ymin, ymax)) or xmax <= xmin or ymax <= ymin:
        return []
    if domain:
        if domain[0] is not None:
            xmin = max(xmin, domain[0])
        if domain[1] is not None:
            xmax = min(xmax, domain[1])
    if xmax <= xmin:
        return []
    height = max(200, min(1600, pixel_width * .7))
    yspan = ymax - ymin
    tolerance = .65 * yspan / height
    bound = max(abs(ymin), abs(ymax), yspan, 1) * 1e6
    cache: dict[float, float] = {}

    def value(x: float) -> float:
        if x not in cache:
            if len(cache) >= 100000:
                return math.nan
            y = expr.evaluate(x)
            cache[x] = y if abs(y) <= bound else math.nan
        return cache[x]

    stream: list[tuple[float, float] | None] = []

    def append(x, y):
        if math.isfinite(y) and ymin - yspan*8 <= y <= ymax + yspan*8:
            p = (x, y)
            if not stream or stream[-1] != p:
                stream.append(p)
        elif not stream or stream[-1] is not None:
            stream.append(None)

    def refine(a: float, ya: float, b: float, yb: float, depth: int = 0):
        m = (a+b) / 2
        ym = value(m)
        finite = all(math.isfinite(y) for y in (ya, ym, yb))
        if finite:
            error = abs(ym - (ya+yb)/2)
            # A steep monotonic straight line is valid; curvature or a sign
            # reversal in the slopes signals a possible pole requiring detail.
            needs = error > tolerance
            outside_same_side = (min(ya, ym, yb) > ymax+yspan*8 or max(ya, ym, yb) < ymin-yspan*8)
            if outside_same_side and error < max(abs(ya), abs(ym), abs(yb))*.01:
                append(a, math.nan)
                return
            if needs and depth < 12 and len(cache) < 99998:
                refine(a, ya, m, ym, depth+1)
                refine(m, ym, b, yb, depth+1)
            elif needs and error > yspan*.1:
                append(a, ya)
                append(m, math.nan)
                append(b, yb)
            else:
                append(a, ya)
                append(m, ym)
                append(b, yb)
        elif depth < 12 and len(cache) < 99998 and (math.isfinite(ya) or math.isfinite(ym) or math.isfinite(yb)):
            refine(a, ya, m, ym, depth+1)
            append(m, ym)
            refine(m, ym, b, yb, depth+1)
        else:
            append(a, ya)
            append(m, math.nan)
            append(b, yb)

    count = max(64, min(1024, int(pixel_width)//3))
    a = xmin
    ya = value(a)
    for i in range(1, count+1):
        b = xmin + (xmax-xmin)*i/count
        yb = value(b)
        refine(a, ya, b, yb)
        a, ya = b, yb
    segments, current = [], []
    for point in stream:
        if point is None:
            if len(current) >= 2:
                segments.append(current)
            current = []
        else:
            current.append(point)
    if len(current) >= 2:
        segments.append(current)
    return segments


def find_intersections(first: str | Callable[[float], float], second: str | Callable[[float], float], xmin: float, xmax: float, radians: bool = True) -> list[tuple[float, float]]:
    """Bracket-and-bisect finite crossings; rejects asymptote sign changes."""
    if not math.isfinite(xmin) or not math.isfinite(xmax) or xmin >= xmax:
        raise ValueError("Intersection search needs a finite increasing X range")
    def safe_function(source):
        function = Expression(source, radians) if isinstance(source, str) else source
        if not callable(function):
            raise ValueError("Intersection functions must be expressions or callables")
        def evaluate(x):
            try:
                value = float(function(x))
                return value if math.isfinite(value) else math.nan
            except (ArithmeticError, ValueError, TypeError):
                return math.nan
        return evaluate
    f, g = safe_function(first), safe_function(second)
    result = []
    count = 2048
    previous_x, previous = xmin, f(xmin)-g(xmin)
    for i in range(1, count+1):
        x = xmin + (xmax-xmin)*i/count
        difference = f(x)-g(x)
        candidate = None
        if math.isfinite(difference) and abs(difference) < 1e-10:
            candidate = x
        elif math.isfinite(previous) and math.isfinite(difference) and previous*difference < 0:
            lo, hi, flo = previous_x, x, previous
            for _ in range(60):
                mid = (lo+hi)/2
                fm = f(mid)-g(mid)
                if not math.isfinite(fm):
                    break
                if abs(fm) < 1e-10:
                    candidate = mid
                    break
                if flo*fm <= 0:
                    hi = mid
                else:
                    lo, flo = mid, fm
            if candidate is None:
                mid = (lo+hi)/2
                if abs(f(mid)-g(mid)) < 1e-7:
                    candidate = mid
        if candidate is not None and (not result or abs(candidate-result[-1][0]) > 1e-6):
            y = f(candidate)
            if math.isfinite(y):
                result.append((candidate, y))
        previous_x, previous = x, difference
    return result
