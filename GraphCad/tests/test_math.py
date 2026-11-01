import math
import pytest

from graphite.data import linear_regression, parse_csv
from graphite.expressions import Expression, ExpressionError, find_intersections, sample_function


@pytest.mark.parametrize("expression,x,expected", [
    ("y = 2x + 3", 4, 11), ("x^2", -3, 9), ("-0.5x+8", 6, 5),
    ("sin(pi/2)", 0, 1), ("sqrt(x)", 9, 3), ("ln(e)", 0, 1),
    ("log(100)", 0, 2), ("abs(x)", -7, 7), ("exp(0)", 1, 1),
    ("acos(0)", 0, math.pi/2), ("2(x+1)(x-1)", 3, 16),
    ("2pi + x sin(x)", math.pi/2, 2.5*math.pi), ("1e3*x", 2, 2000),
    ("-x^2", 3, -9), ("2^3^2", 0, 512)])
def test_expression_supported_operations(expression, x, expected):
    assert Expression(expression).evaluate(x) == pytest.approx(expected)


@pytest.mark.parametrize("source", ["", "y =", "x +", "sin(x,x)", "foo(x)", "x.__class__",
                                       "__import__('os')", "[x]", "x[0]", "lambda:x", "x=3", "9e999"])
def test_invalid_and_unsafe_expressions_rejected(source):
    with pytest.raises(ExpressionError):
        Expression(source)


def test_undefined_regions_return_nan_and_degree_mode():
    assert math.isnan(Expression("sqrt(x)").evaluate(-1))
    assert math.isnan(Expression("1/x").evaluate(0))
    assert math.isnan(Expression("exp(x)").evaluate(1000))
    assert Expression("sin(x)", radians=False).evaluate(90) == pytest.approx(1)
    assert Expression("asin(x)", radians=False).evaluate(1) == pytest.approx(90)


def test_linear_quadratic_and_trig_sampling_accuracy():
    for source in ("2x+3", "x^2", "sin(x)"):
        segments = sample_function(source, -3, 3, -10, 12, pixel_width=600)
        assert len(segments) == 1
        expr = Expression(source)
        assert all(y == pytest.approx(expr(x)) for x, y in segments[0])
        assert segments[0][0][0] == -3
        assert segments[0][-1][0] == 3


def test_domain_and_undefined_region_sampling():
    segments = sample_function("sqrt(x)", -10, 10, -1, 5, domain=(0, 4))
    assert segments and all(0 <= x <= 4 for seg in segments for x, y in seg)
    assert all(math.isfinite(y) for seg in segments for x, y in seg)
    assert not sample_function("x", 0, 10, 0, 10, domain=(20, 30))


@pytest.mark.parametrize("source,poles", [("1/x", [0]), ("1/(x-0.12345)", [.12345]), ("tan(x)", [-math.pi/2, math.pi/2])])
def test_no_segment_connects_across_vertical_asymptote(source, poles):
    segments = sample_function(source, -3, 3, -10, 10, pixel_width=700)
    assert len(segments) >= len(poles)+1
    for segment in segments:
        for a, b in zip(segment, segment[1:]):
            assert not any(a[0] < pole < b[0] for pole in poles)


def test_zoom_resampling_preserves_equation_and_refines_curvature():
    broad = sample_function("sin(20x)", -10, 10, -2, 2, pixel_width=300)
    zoomed = sample_function("sin(20x)", -.1, .1, -2, 2, pixel_width=1200)
    assert zoomed[0][0][0] == -.1 and zoomed[0][-1][0] == .1
    assert len(zoomed[0]) > 300
    for a, b in zip(zoomed[0], zoomed[0][1:]):
        actual = math.sin(20*(a[0]+b[0])/2)
        assert abs(actual-(a[1]+b[1])/2) < .005


def test_numerical_intersections_and_asymptote_rejection():
    roots = find_intersections("x^2", "4", -3, 3)
    assert [x for x, y in roots] == pytest.approx([-2, 2])
    assert find_intersections("1/(x-.12345)", "0", -3, 3) == []


def test_intersections_callables_account_for_offsets_and_domains():
    base = Expression("x^2")
    shifted = lambda x: base(x-2)+1 if 2 <= x <= 6 else math.nan
    roots = find_intersections(shifted, "5", -5, 10)
    assert len(roots) == 1
    assert roots[0] == pytest.approx((4, 5))
    assert find_intersections(lambda x: math.nan, "x", -5, 5) == []
    assert find_intersections(lambda x: 1/x, "0", -2, 2) == []


def test_csv_headers_tabs_bom_and_strict_error_rows():
    assert parse_csv("\ufeffX,Y\n1,3\n2,5\n\n3,7\n") == [[1, 3], [2, 5], [3, 7]]
    assert parse_csv("1\t2\n3\t4") == [[1, 2], [3, 4]]
    assert parse_csv("X;Y\n1;2") == [[1, 2]]
    with pytest.raises(ValueError, match="Row 3"):
        parse_csv("X,Y\n1,2\nwrong,7")


@pytest.mark.parametrize("source", ["", "x,y\n", "1,2,3", "1,nan", "inf,1", '1,"unclosed'])
def test_invalid_csv_rejected(source):
    with pytest.raises(ValueError):
        parse_csv(source)


def test_regression_equation_statistics_and_linked_update():
    rows = [[1, 3], [2, 5], [3, 7], [4, 9]]
    result = linear_regression(rows)
    assert result.slope == 2
    assert result.intercept == 1
    assert result.r_squared == 1
    assert result.equation == "y = 2x + 1"
    rows[-1][1] = 10
    updated = linear_regression(rows)
    assert updated.slope == pytest.approx(2.3)
    assert updated.intercept == pytest.approx(.5)
    assert updated.r_squared == pytest.approx(.988785046728972)


def test_regression_centered_for_large_offsets_and_constant_response():
    result = linear_regression([[1e10+i, 3*i+4] for i in range(10)])
    assert result.slope == pytest.approx(3)
    assert result.intercept == pytest.approx(4-3e10)
    assert result.r_squared == 1
    assert linear_regression([[1, 7], [2, 7], [3, 7]]).r_squared == 1


@pytest.mark.parametrize("rows", [[], [[1, 2]], [[1, 2], [1, 3]], [[0, 0], [math.nan, 2]]])
def test_degenerate_regression_rejected(rows):
    with pytest.raises(ValueError):
        linear_regression(rows)
