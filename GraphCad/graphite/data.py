"""Strict CSV/TSV ingestion and numerically centered linear least squares."""
from __future__ import annotations
import csv
from dataclasses import asdict, dataclass
import io
import math


def validate_rows(rows) -> list[list[float]]:
    if not isinstance(rows, (list, tuple)) or len(rows) > 200000:
        raise ValueError("Dataset must contain at most 200,000 rows")
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError(f"Row {index}: expected exactly two columns (X and Y)")
        try:
            if any(isinstance(value, bool) for value in row):
                raise ValueError
            x, y = float(row[0]), float(row[1])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Row {index}: X and Y must be numeric") from exc
        if not math.isfinite(x) or not math.isfinite(y) or max(abs(x), abs(y)) > 1e12:
            raise ValueError(f"Row {index}: X and Y must be finite and within ±1e12")
        result.append([x, y])
    return result


def parse_csv(text: str) -> list[list[float]]:
    if not isinstance(text, str) or len(text) > 32*1024*1024:
        raise ValueError("CSV input exceeds the 32 MB size limit")
    text = text.lstrip("\ufeff")
    sample = text[:8192]
    delimiter = "\t" if "\t" in sample else ";" if ";" in sample and "," not in sample else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    rows = []
    first = True
    try:
        for raw in reader:
            if not raw or all(not value.strip() for value in raw):
                continue
            if len(raw) != 2:
                raise ValueError(f"Row {reader.line_num}: expected exactly two columns (X and Y)")
            if first and raw[0].strip().lower() in {"x", "quantity", "time"} and raw[1].strip().lower() in {"y", "price", "value"}:
                first = False
                continue
            first = False
            try:
                row = validate_rows([raw])[0]
            except ValueError as exc:
                raise ValueError(f"Row {reader.line_num}: {str(exc).partition(': ')[2]}") from exc
            rows.append(row)
            if len(rows) > 200000:
                raise ValueError("Dataset exceeds 200,000 rows")
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV at row {reader.line_num}: {exc}") from exc
    if not rows:
        raise ValueError("Dataset contains no numeric rows")
    return rows


@dataclass(frozen=True)
class Regression:
    slope: float
    intercept: float
    r_squared: float
    equation: str
    count: int
    r: float | None = None

    def to_dict(self):
        return asdict(self)


def pearson_correlation(rows) -> float | None:
    """Centered product moment correlation; undefined for <2 or constant variables."""
    values=validate_rows(rows)
    if len(values)<2:return None
    mx=math.fsum(x for x,_ in values)/len(values)
    my=math.fsum(y for _,y in values)/len(values)
    xx=math.fsum((x-mx)**2 for x,_ in values)
    yy=math.fsum((y-my)**2 for _,y in values)
    if xx==0 or yy==0:return None
    xy=math.fsum((x-mx)*(y-my) for x,y in values)
    return max(-1.0,min(1.0,(xy/math.sqrt(xx))/math.sqrt(yy)))


def format_correlation(value):
    return 'undefined' if value is None else f'{value:.8g}'


def linear_regression(rows) -> Regression:
    values = validate_rows(rows)
    if len(values) < 2:
        raise ValueError("Linear regression needs at least two data points")
    n = len(values)
    mx, my = math.fsum(x for x, _ in values)/n, math.fsum(y for _, y in values)/n
    xx = math.fsum((x-mx)**2 for x, _ in values)
    if xx == 0:
        raise ValueError("Linear regression needs at least two different X values")
    xy = math.fsum((x-mx)*(y-my) for x, y in values)
    slope = xy/xx
    intercept = my-slope*mx
    total = math.fsum((y-my)**2 for _, y in values)
    residual = math.fsum(((y-my)-slope*(x-mx))**2 for x, y in values)
    # A constant response is fitted exactly; adopt sklearn's finite R²=1
    # convention rather than divide by zero.
    r_squared = 1.0 if total == 0 else min(1.0, max(0.0, 1-residual/total))
    sign = "+" if intercept >= 0 else "−"
    equation = f"y = {slope:.8g}x {sign} {abs(intercept):.8g}"
    return Regression(slope, intercept, r_squared, equation, n, pearson_correlation(values))
