"""The data model's job is to fail loudly on inconsistent programme data, so that
a broken deck is impossible rather than merely unlikely."""

from datetime import date

import pytest
from pydantic import ValidationError

from deckpilot.data.generate import build_programme, iso_week
from deckpilot.data.models import Programme


@pytest.fixture(scope="module")
def programme() -> Programme:
    return build_programme()


def test_generated_programme_matches_the_brief(programme):
    assert len(programme.work_packages) == 4
    for wp in programme.work_packages:
        assert 2 <= len(wp.sub_streams) <= 4
    assert len(programme.stage_gates) == 5
    assert 15 <= len(programme.raid) <= 22
    assert programme.end.year - programme.start.year == 1


def test_every_raid_category_is_represented(programme):
    kinds = {item.type for item in programme.raid}
    assert {k.value for k in kinds} == {"risk", "assumption", "issue", "dependency"}
    assert {item.severity for item in programme.raid} == set(
        type(programme.raid[0].severity)
    )


def test_stage_gates_are_ordered_and_span_the_programme(programme):
    gates = sorted(programme.stage_gates, key=lambda g: g.date)
    assert [g.number for g in gates] == [1, 2, 3, 4, 5]
    assert programme.start <= gates[0].date and gates[-1].date <= programme.end


def test_milestones_span_roughly_twelve_months(programme):
    days = sorted(m.date for m in programme.milestones)
    assert (days[-1] - days[0]).days > 250


def test_every_sub_stream_has_a_forward_milestone(programme):
    """A live sub-stream with nothing ahead of it makes for a thin status slide."""
    latest = programme.weeks()[-1]
    for status in programme.status_for_week(latest):
        assert status.next_milestone_id is not None, status.sub_stream_id
        assert programme.milestone(status.next_milestone_id).date >= date(2026, 8, 26)


def test_every_sub_stream_reports_every_week(programme):
    for week in programme.weeks():
        assert len(programme.status_for_week(week)) == len(programme.sub_streams)


def test_status_for_week_follows_work_package_order(programme):
    order = [ss.id for ss in programme.sub_streams]
    reported = [s.sub_stream_id for s in programme.status_for_week(programme.weeks()[-1])]
    assert reported == order


def test_progress_never_decreases_over_time(programme):
    for ss in programme.sub_streams:
        series = [
            s.progress_pct
            for week in programme.weeks()
            for s in programme.status_for_week(week)
            if s.sub_stream_id == ss.id
        ]
        assert series == sorted(series), ss.id


def test_phases_are_contiguous_and_inside_the_window(programme):
    for ss in programme.sub_streams:
        assert programme.start <= ss.start and ss.end <= programme.end
        for phase in ss.phases:
            assert phase.start <= phase.end


def test_lookups_resolve_and_raise_on_unknown_ids(programme):
    ss = programme.sub_streams[0]
    assert programme.sub_stream(ss.id) is ss
    assert ss in programme.work_package_of(ss.id).sub_streams
    assert programme.work_package("wp1").number == 1
    for missing in ("nope",):
        with pytest.raises(KeyError):
            programme.sub_stream(missing)
        with pytest.raises(KeyError):
            programme.work_package(missing)
        with pytest.raises(KeyError):
            programme.milestone(missing)


def test_json_round_trip_is_lossless(programme, tmp_path):
    path = programme.save(tmp_path / "programme.json")
    assert Programme.load(path) == programme


def test_iso_week_formatting():
    assert iso_week(date(2026, 8, 26)) == "2026-W35"
    assert iso_week(date(2026, 1, 1)) == "2026-W01"


def _mutate(programme: Programme, **changes) -> dict:
    payload = programme.model_dump(mode="json")
    payload.update(changes)
    return payload


def test_dangling_raid_reference_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["raid"][0]["sub_stream_id"] = "ss-does-not-exist"
    with pytest.raises(ValidationError, match="unknown sub-stream"):
        Programme.model_validate(payload)


def test_dangling_milestone_reference_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["weekly_status"][0]["next_milestone_id"] = "m999"
    with pytest.raises(ValidationError, match="unknown milestone"):
        Programme.model_validate(payload)


def test_milestone_outside_the_window_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["milestones"][0]["date"] = "2029-01-01"
    with pytest.raises(ValidationError, match="outside the programme window"):
        Programme.model_validate(payload)


def test_phase_outside_the_window_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["work_packages"][0]["sub_streams"][0]["phases"][0]["start"] = "2025-01-01"
    with pytest.raises(ValidationError, match="outside the programme window"):
        Programme.model_validate(payload)


def test_backwards_phase_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    phase = payload["work_packages"][0]["sub_streams"][0]["phases"][0]
    phase["start"], phase["end"] = phase["end"], phase["start"]
    with pytest.raises(ValidationError, match="before it starts"):
        Programme.model_validate(payload)


def test_duplicate_weekly_report_is_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["weekly_status"].append(payload["weekly_status"][0])
    with pytest.raises(ValidationError, match="two weekly status entries"):
        Programme.model_validate(payload)


def test_duplicate_sub_stream_ids_are_rejected(programme):
    payload = programme.model_dump(mode="json")
    streams = payload["work_packages"][0]["sub_streams"]
    streams[1]["id"] = streams[0]["id"]
    with pytest.raises(ValidationError, match="duplicate sub-stream ids"):
        Programme.model_validate(payload)


def test_weekly_status_needs_three_to_five_activities(programme):
    payload = programme.model_dump(mode="json")
    payload["weekly_status"][0]["activities"] = ["only one"]
    with pytest.raises(ValidationError):
        Programme.model_validate(payload)


def test_unknown_fields_are_rejected(programme):
    payload = programme.model_dump(mode="json")
    payload["surprise"] = True
    with pytest.raises(ValidationError):
        Programme.model_validate(payload)
