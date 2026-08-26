"""Benefit measures, and the scorecard that reports them.

The interesting logic is attainment: a measure can improve by going up or by
going down, can overshoot, and can move backwards. All three have to produce a
number a progress bar can draw without escaping its track.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from deckpilot.data.generate import build_programme
from deckpilot.data.models import BenefitDirection, BenefitMeasure, Programme
from deckpilot.specgen import fallback


def measure(**overrides) -> BenefitMeasure:
    base = {
        "id": "b1",
        "name": "Touchless invoice rate",
        "unit": "%",
        "baseline": 40.0,
        "current": 50.0,
        "target": 80.0,
        "owner": "A Person",
        "sub_stream_id": "ss22",
        "direction": BenefitDirection.UP,
        "as_of": date(2026, 8, 28),
    }
    return BenefitMeasure(**{**base, **overrides})


@pytest.fixture(scope="module")
def programme() -> Programme:
    return build_programme()


# -- attainment ------------------------------------------------------------


def test_an_upward_measure_attains_toward_a_higher_target():
    assert measure(baseline=40, current=50, target=80).attainment == pytest.approx(0.25)


def test_a_downward_measure_attains_toward_a_lower_target():
    m = measure(baseline=54, current=49, target=47, direction=BenefitDirection.DOWN)
    assert m.attainment == pytest.approx(5 / 7)


def test_a_measure_at_its_baseline_has_attained_nothing():
    assert measure(current=40).attainment == 0.0


def test_a_measure_at_its_target_has_attained_everything():
    assert measure(current=80).attainment == 1.0


def test_an_overshoot_is_clamped_to_the_track():
    assert measure(current=95).attainment == 1.0


def test_moving_backwards_clamps_to_zero_but_is_reported():
    m = measure(current=30)
    assert m.attainment == 0.0
    assert m.moved_backwards is True
    assert measure(current=50).moved_backwards is False


def test_a_downward_measure_moving_the_wrong_way_is_detected():
    m = measure(baseline=54, current=58, target=47, direction=BenefitDirection.DOWN)
    assert m.attainment == 0.0
    assert m.moved_backwards is True


# -- validation ------------------------------------------------------------


def test_a_target_equal_to_the_baseline_is_rejected():
    with pytest.raises(ValidationError, match="target equal to its baseline"):
        measure(target=40)


def test_a_direction_that_contradicts_the_target_is_rejected():
    with pytest.raises(ValidationError, match="moves the other way"):
        measure(direction=BenefitDirection.DOWN)  # target 80 is above baseline 40
    with pytest.raises(ValidationError, match="moves the other way"):
        measure(baseline=54, current=50, target=47, direction=BenefitDirection.UP)


def test_a_benefit_pointing_at_an_unknown_sub_stream_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"][0]["sub_stream_id"] = "nope"
    with pytest.raises(ValidationError, match="unknown sub-stream"):
        Programme.model_validate(payload)


def test_a_benefit_measured_outside_the_window_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"][0]["as_of"] = "2029-01-01"
    with pytest.raises(ValidationError, match="outside the programme window"):
        Programme.model_validate(payload)


def test_duplicate_benefit_ids_are_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"][1]["id"] = payload["benefits"][0]["id"]
    with pytest.raises(ValidationError, match="duplicate benefit ids"):
        Programme.model_validate(payload)


def test_a_programme_without_benefits_is_still_valid(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"] = []
    assert Programme.model_validate(payload).benefits == []


# -- formatting ------------------------------------------------------------


def test_values_print_without_trailing_zeros():
    m = measure(unit="days", baseline=9, current=7.5, target=7,
                direction=BenefitDirection.DOWN)
    assert m.plain(9) == "9"
    assert m.plain(7.5) == "7.5"
    assert m.format(7.5) == "7.5 days"
    assert measure().format(50) == "50%"


def test_the_unit_moves_into_the_name_unless_it_is_a_percentage():
    assert measure().display_name == "Touchless invoice rate"
    assert measure(unit="days").display_name == "Touchless invoice rate (days)"


def test_a_unit_the_name_already_carries_is_not_repeated():
    m = measure(name="Change readiness index", unit="index")
    assert m.display_name == "Change readiness index"


# -- the generated set -----------------------------------------------------


def test_the_generated_benefits_are_a_mixed_picture(programme):
    """A scorecard where every measure agrees with the plan is not believable."""
    week = programme.weeks()[-1]
    progress = {s.sub_stream_id: s.progress_pct / 100 for s in programme.status_for_week(week)}
    ahead = [b for b in programme.benefits if b.attainment >= progress[b.sub_stream_id]]
    behind = [b for b in programme.benefits if b.attainment < progress[b.sub_stream_id]]
    assert ahead and behind


def test_elapsed_fraction_spans_the_window(programme):
    assert programme.elapsed_fraction(programme.start) == 0.0
    assert programme.elapsed_fraction(programme.end) == 1.0
    assert 0.5 < programme.elapsed_fraction(date(2026, 8, 28)) < 0.65
    assert programme.elapsed_fraction(date(2020, 1, 1)) == 0.0
    assert programme.elapsed_fraction(date(2030, 1, 1)) == 1.0


def test_benefit_lookup_raises_on_an_unknown_id(programme):
    assert programme.benefit("b1").id == "b1"
    with pytest.raises(KeyError):
        programme.benefit("nope")


# -- the spec --------------------------------------------------------------


def test_every_benefit_reaches_the_scorecard(programme):
    spec = fallback.kpi_scorecard(programme, programme.weeks()[-1])
    assert len(spec.rows) == len(programme.benefits)
    assert {r.name for r in spec.rows} == {b.display_name for b in programme.benefits}


def test_the_expected_marker_is_the_producing_streams_progress(programme):
    week = programme.weeks()[-1]
    spec = fallback.kpi_scorecard(programme, week)
    progress = {s.sub_stream_id: s.progress_pct / 100 for s in programme.status_for_week(week)}
    for row, benefit in zip(spec.rows, programme.benefits, strict=True):
        assert row.expected == pytest.approx(progress[benefit.sub_stream_id])


def test_a_programme_with_no_benefits_produces_no_scorecard(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"] = []
    assert fallback.kpi_scorecard(Programme.model_validate(payload), programme.weeks()[-1]) is None


def test_the_deck_omits_the_scorecard_when_there_is_nothing_to_score(programme):
    payload = programme.model_dump(mode="json")
    payload["benefits"] = []
    spec = fallback.build_deck_spec(Programme.model_validate(payload))
    assert not any(s.layout == "kpi_scorecard" for s in spec.slides)
    assert all(s is not None for s in spec.slides)
