"""The cost bridge.

A waterfall is the exhibit a CFO reads first and the easiest one to draw
dishonestly, so the arithmetic is checked as arithmetic: the bridge reconciles,
every column spans the levels either side of it, and no step is silently dropped
for being too small to see.
"""

import pytest
from pydantic import ValidationError

from deckpilot.data.generate import build_programme
from deckpilot.data.models import Programme
from deckpilot.renderer import benefits_bridge
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
    return SAMPLES["benefits_bridge"]


# -- the case ---------------------------------------------------------------


def test_the_case_reconciles(programme):
    case = programme.benefit_case
    assert case is not None
    assert case.baseline + sum(lever.value for lever in case.levers) == pytest.approx(
        case.target
    )


def test_a_case_that_does_not_bridge_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["benefit_case"]["target"] = 20.0
    with pytest.raises(ValidationError, match="does not bridge"):
        Programme.model_validate(payload)


def test_a_lever_pointing_at_an_unknown_sub_stream_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["benefit_case"]["levers"][0]["sub_stream_id"] = "nope"
    with pytest.raises(ValidationError, match="unknown sub-stream"):
        Programme.model_validate(payload)


def test_running_totals_walk_from_baseline_to_target(programme):
    case = programme.benefit_case
    totals = case.running_totals
    assert totals[0] == case.baseline
    assert totals[-1] == pytest.approx(case.target)
    assert len(totals) == len(case.levers) + 1


def test_the_case_includes_a_lever_that_adds_cost(programme):
    """A bridge of pure savings has forgotten what the new model costs to run."""
    assert any(not lever.is_saving for lever in programme.benefit_case.levers)


def test_a_short_name_trims_to_the_first_idea(programme):
    lever = next(
        lever for lever in programme.benefit_case.levers if " and " in lever.name
    )
    assert lever.short_name == lever.name.split(" and ")[0]
    assert len(lever.short_name) < len(lever.name)


# -- the spec ---------------------------------------------------------------


def test_the_spec_opens_and_closes_on_an_anchor(spec):
    assert spec.steps[0].kind == "anchor"
    assert spec.steps[-1].kind == "anchor"
    assert all(s.kind != "anchor" for s in spec.steps[1:-1])


def test_every_lever_becomes_a_step(programme, spec):
    assert len(spec.steps) == len(programme.benefit_case.levers) + 2


def test_each_step_spans_the_levels_either_side_of_it(programme, spec):
    totals = programme.benefit_case.running_totals
    for step, before, after in zip(spec.steps[1:-1], totals[:-1], totals[1:], strict=True):
        assert step.from_value == pytest.approx(before)
        assert step.to_value == pytest.approx(after)


def test_savings_and_increases_are_typed_apart(programme, spec):
    for step, lever in zip(spec.steps[1:-1], programme.benefit_case.levers, strict=True):
        assert step.kind == ("decrease" if lever.is_saving else "increase")


def test_the_slide_says_the_axis_is_truncated(spec):
    assert "truncated" in spec.subtitle.lower()


def test_the_title_names_the_reduction_and_the_biggest_lever(programme, spec):
    case = programme.benefit_case
    assert f"{case.total_saving / case.baseline:.0%}" in spec.title
    largest = min(case.levers, key=lambda lever: lever.value)
    assert largest.short_name.lower() in spec.title.lower()


def test_low_confidence_value_is_called_out(programme, spec):
    low = [lever for lever in programme.benefit_case.levers if lever.confidence.value == "low"]
    if low:
        assert any("low-confidence" in c for c in spec.considerations)


def test_a_programme_without_a_case_produces_no_bridge(programme):
    payload = programme.model_dump(mode="json")
    payload["benefit_case"] = None
    trimmed = Programme.model_validate(payload)
    assert fallback.benefits_bridge(trimmed, trimmed.weeks()[-1]) is None
    deck_spec = fallback.build_deck_spec(trimmed)
    assert not any(s.layout == "benefits_bridge" for s in deck_spec.slides)


# -- the drawing ------------------------------------------------------------


def render(spec):
    return benefits_bridge.render(new_deck(), spec, page=6)


def test_the_bridge_is_geometrically_clean(spec):
    assert [f for f in check_slide(6, render(spec)) if f.severity == "error"] == []


def test_the_axis_leaves_room_below_the_lowest_level(spec):
    floor, ceiling = benefits_bridge.axis_range(spec.steps)
    levels = [v for s in spec.steps for v in (s.from_value, s.to_value)]
    assert floor < min(levels)
    assert ceiling > max(levels)


def test_bar_heights_are_proportional_to_their_steps(spec):
    slide = render(spec)
    floor, ceiling = benefits_bridge.axis_range(spec.steps)
    chart_h = (
        T.content_bottom() - T.BRIDGE_LABEL_BAND_H - T.content_top() - T.BRIDGE_VALUE_BAND_H
    )
    scale = chart_h / (ceiling - floor)

    for i, step in enumerate(spec.steps):
        bar = next(s for s in slide.shapes if s.name == f"step{i}:bar")
        if step.kind == "anchor":
            expected = (step.to_value - floor) * scale
        else:
            expected = abs(step.to_value - step.from_value) * scale
        assert bar.height == pytest.approx(max(T.BRIDGE_MIN_BAR_H, expected), abs=2)


def test_a_step_too_small_to_see_is_still_drawn(spec):
    """Dropping it would leave an unexplained gap in the bridge."""
    slide = render(spec)
    tiny = min(
        (s for s in spec.steps if s.kind != "anchor"),
        key=lambda s: abs(s.to_value - s.from_value),
    )
    index = spec.steps.index(tiny)
    bar = next(s for s in slide.shapes if s.name == f"step{index}:bar")
    assert bar.height >= T.BRIDGE_MIN_BAR_H


def test_columns_are_joined_by_a_connector_at_the_running_level(spec):
    slide = render(spec)
    connectors = [s for s in slide.shapes if s.shape_type == 9 and s.height == 0]
    assert len(connectors) == len(spec.steps) - 1


def test_savings_are_green_and_increases_are_red(spec):
    slide = render(spec)
    for i, step in enumerate(spec.steps):
        bar = next(s for s in slide.shapes if s.name == f"step{i}:bar")
        assert bar.fill.fore_color.rgb == benefits_bridge.STEP_COLORS[step.kind]


def test_no_column_escapes_the_chart_area(spec):
    slide = render(spec)
    bars = [s for s in slide.shapes if s.name.endswith(":bar")]
    assert bars
    for bar in bars:
        assert bar.top >= T.content_top()
        assert bar.top + bar.height <= T.content_bottom() - T.BRIDGE_LABEL_BAND_H + 1
