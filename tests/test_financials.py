"""Programme budget.

Two things a finance table has to get right: the arithmetic has to tie, and it
has to say which line is the problem before anyone reads a figure. The first is
tested here; the second is why the variance column is a diverging bar.
"""

import pytest
from pydantic import ValidationError

from deckpilot.data.generate import build_programme
from deckpilot.data.models import Programme
from deckpilot.renderer import financial_summary
from deckpilot.renderer.base import new_deck
from deckpilot.renderer.qa import check_slide
from deckpilot.specgen import fallback
from deckpilot.specgen.samples import SAMPLES
from deckpilot.theme import tokens as T


@pytest.fixture(scope="module")
def programme() -> Programme:
    return build_programme()


@pytest.fixture(scope="module")
def spec():
    return SAMPLES["financial_summary"]


# -- the budget -------------------------------------------------------------


def test_variance_is_forecast_less_budget(programme):
    for line in programme.budget.lines:
        assert line.variance == pytest.approx(line.forecast - line.budget)


def test_the_total_ties_to_its_lines(programme):
    budget = programme.budget
    assert budget.total("budget") == pytest.approx(sum(x.budget for x in budget.lines))
    assert budget.total("forecast") == pytest.approx(sum(x.forecast for x in budget.lines))
    assert budget.variance == pytest.approx(
        budget.total("forecast") - budget.total("budget")
    )


def test_the_contingency_line_is_singled_out(programme):
    budget = programme.budget
    assert budget.contingency is not None
    assert budget.contingency not in budget.delivery_lines
    assert len(budget.delivery_lines) == len(budget.lines) - 1


def test_two_contingency_lines_are_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["budget"]["lines"][0]["is_contingency"] = True
    with pytest.raises(ValidationError, match="at most one contingency line"):
        Programme.model_validate(payload)


def test_contingency_drawn_is_the_share_consumed(programme):
    line = programme.budget.contingency
    expected = (line.budget - line.forecast) / line.budget
    assert programme.budget.contingency_drawn == pytest.approx(expected)


def test_contingency_drawn_stays_inside_its_track(programme):
    payload = programme.model_dump(mode="json")
    for forecast in (-5.0, 0.0, 99.0):
        payload["budget"]["lines"][-1]["forecast"] = forecast
        assert 0.0 <= Programme.model_validate(payload).budget.contingency_drawn <= 1.0


def test_the_budget_carries_a_real_overrun(programme):
    """A budget where every line lands on plan is a budget nobody is managing."""
    assert any(line.variance > 0 for line in programme.budget.delivery_lines)


# -- the spec ---------------------------------------------------------------


def test_every_line_becomes_a_row_plus_a_total(programme, spec):
    assert len(spec.rows) == len(programme.budget.lines)
    assert spec.total.emphasis is True


def test_figures_are_bare_and_keep_their_decimal(spec):
    for row in [*spec.rows, spec.total]:
        for value in (row.budget, row.actual, row.forecast):
            assert "EUR" not in value
            assert "." in value, value


def test_a_variance_inside_a_rounding_step_shows_as_a_dash(spec):
    """Better a dash than "-0.0", which reads like a defect."""
    for row in [*spec.rows, spec.total]:
        if row.variance == "-":
            assert row.variance_value == 0
        else:
            assert row.variance_value != 0
            assert row.variance[0] in "+-"


def test_the_title_compares_contingency_with_elapsed_time(programme, spec):
    drawn = programme.budget.contingency_drawn
    elapsed = programme.elapsed_fraction(fallback.week_end(programme.weeks()[-1]))
    assert f"{drawn:.0%}" in spec.title
    assert f"{elapsed:.0%}" in spec.title


def test_the_gauges_carry_the_same_two_numbers(programme, spec):
    assert [g.label for g in spec.gauges] == ["Contingency drawn", "Programme elapsed"]
    assert spec.gauges[0].fraction == pytest.approx(programme.budget.contingency_drawn)


def test_a_programme_without_a_budget_produces_no_slide(programme):
    payload = programme.model_dump(mode="json")
    payload["budget"] = None
    trimmed = Programme.model_validate(payload)
    assert fallback.financial_summary(trimmed, trimmed.weeks()[-1]) is None
    assert not any(
        s.layout == "financial_summary" for s in fallback.build_deck_spec(trimmed).slides
    )


# -- the drawing ------------------------------------------------------------


def render(spec):
    return financial_summary.render(new_deck(), spec, page=7)


def test_the_summary_is_geometrically_clean(spec):
    assert [f for f in check_slide(7, render(spec)) if f.severity == "error"] == []


def test_overruns_point_right_and_underspend_points_left(spec):
    slide = render(spec)
    body = [*spec.rows, spec.total]
    for i, row in enumerate(body):
        bars = [s for s in slide.shapes if s.name == f"marker:fin{i}var"]
        if row.variance_value == 0:
            assert not bars
            continue
        bar = bars[0]
        zero = next(
            s for s in slide.shapes
            if s.shape_type == 9 and s.width == 0 and abs(s.top - bar.top) < T.inches(0.02)
        )
        if row.variance_value > 0:
            assert bar.left >= zero.left - 1
        else:
            assert bar.left + bar.width <= zero.left + 1


def test_bar_length_is_proportional_to_the_variance(spec):
    slide = render(spec)
    body = [*spec.rows, spec.total]
    pairs = []
    for i, row in enumerate(body):
        bars = [s for s in slide.shapes if s.name == f"marker:fin{i}var"]
        if bars and abs(row.variance_value) > 0.2:
            pairs.append((abs(row.variance_value), bars[0].width))
    assert len(pairs) >= 2
    ratios = [width / value for value, width in pairs]
    assert max(ratios) == pytest.approx(min(ratios), rel=0.05)


def test_overruns_are_red_and_underspend_green(spec):
    slide = render(spec)
    for i, row in enumerate([*spec.rows, spec.total]):
        for bar in [s for s in slide.shapes if s.name == f"marker:fin{i}var"]:
            assert bar.fill.fore_color.rgb == financial_summary.variance_colour(
                row.variance_value
            )


def test_the_gauges_share_one_scale(spec):
    slide = render(spec)
    tracks = [s for s in slide.shapes if s.name.endswith(":track")]
    assert len({t.width for t in tracks}) == 1
    assert len({t.left for t in tracks}) == 1
    for i, gauge in enumerate(spec.gauges):
        fill = next(s for s in slide.shapes if s.name == f"marker:gauge{i}fill")
        track = next(s for s in slide.shapes if s.name == f"gauge{i}:track")
        assert fill.width == pytest.approx(track.width * gauge.fraction, abs=2)
