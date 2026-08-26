"""The deterministic builder is what CI and `deckpilot demo` run, and it is the
reference the LLM path has to match. So it is tested for two things: that it
always produces a schema-valid deck, and that its titles actually say something
about the numbers rather than being fixed strings."""

from datetime import date

import pytest

from deckpilot.data.generate import build_programme
from deckpilot.data.models import RAG, Programme
from deckpilot.specgen import fallback
from deckpilot.specgen.schema import DeckSpec


@pytest.fixture(scope="module")
def programme() -> Programme:
    return build_programme()


@pytest.fixture(scope="module")
def spec(programme) -> DeckSpec:
    return fallback.build_deck_spec(programme)


def test_the_deck_validates_against_its_own_schema(spec):
    assert DeckSpec.model_validate(spec.model_dump(mode="json")) == spec


def test_the_deck_is_built_for_the_latest_week_by_default(programme, spec):
    assert spec.week == programme.weeks()[-1]


def test_every_week_with_data_produces_a_valid_deck(programme):
    for week in programme.weeks():
        built = fallback.build_deck_spec(programme, week)
        assert DeckSpec.model_validate(built.model_dump(mode="json"))
        assert built.week == week


def test_a_week_with_no_data_is_refused(programme):
    with pytest.raises(ValueError, match="no status reported"):
        fallback.build_deck_spec(programme, "1999-W01")


def test_the_build_is_deterministic(programme):
    a = fallback.build_deck_spec(programme, "2026-W34")
    b = fallback.build_deck_spec(programme, "2026-W34")
    assert a == b


def test_the_deck_leads_with_the_answer(spec):
    """A status deck opens on the verdict, not on a divider."""
    layouts = [s.layout for s in spec.slides]
    assert layouts[0] == "exec_summary"
    assert layouts.count("section_divider") >= 3


def test_the_deck_covers_every_layout(spec):
    layouts = {s.layout for s in spec.slides}
    from deckpilot.renderer.deck import RENDERERS

    assert layouts == set(RENDERERS), sorted(set(RENDERERS) - layouts)


def test_the_deck_is_long_enough_to_present(spec):
    assert len(spec.slides) >= 12


def test_section_dividers_are_numbered_in_order(spec):
    numbers = [s.number for s in spec.slides if s.layout == "section_divider"]
    assert numbers == [str(i) for i in range(1, len(numbers) + 1)]


# -- content selection -----------------------------------------------------


def test_raid_is_ranked_worst_first(programme):
    ranked = fallback.rank_raid(programme.raid)
    severities = [r.severity.value for r in ranked]
    assert severities == sorted(severities, key=lambda s: "HML".index(s))
    highs = [r for r in ranked if r.severity.value == "H"]
    assert [r.due for r in highs] == sorted(r.due for r in highs)


def test_considerations_are_drawn_from_the_relevant_work_package(programme, spec):
    charters = [s for s in spec.slides if s.layout == "workstream_charter"]
    assert charters
    for charter in charters:
        number = charter.columns[0].number.split(".")[0]
        wp = next(w for w in programme.work_packages if str(w.number) == number)
        names = {i.title for i in programme.raid if i.sub_stream_id in
                 {ss.id for ss in wp.sub_streams}}
        for line in charter.considerations:
            assert any(line.startswith(name) for name in names), line


def test_a_work_package_too_small_for_the_layout_gets_no_charter(programme, spec):
    """The charter needs at least three columns; a two-sub-stream work package
    gets left out rather than stretched."""
    small = [wp for wp in programme.work_packages if len(wp.sub_streams) < 3]
    assert small, "the fixture should include one, or this test proves nothing"
    charters = [s for s in spec.slides if s.layout == "workstream_charter"]
    assert len(charters) == len(programme.work_packages) - len(small)
    rendered_names = {c.name for s in charters for c in s.columns}
    for wp in small:
        assert not any(ss.name in rendered_names for ss in wp.sub_streams)


def test_every_charter_column_carries_its_current_position(programme, spec):
    charters = [s for s in spec.slides if s.layout == "workstream_charter"]
    for charter in charters:
        for column in charter.columns:
            assert any("% complete" in o for o in column.outcomes), column.name
            assert any(o.startswith("Next:") for o in column.outcomes), column.name


def test_bullets_carry_no_terminal_full_stop(spec):
    charters = [s for s in spec.slides if s.layout == "workstream_charter"]
    for charter in charters:
        for column in charter.columns:
            for line in column.activities + column.outcomes:
                assert not line.endswith("."), line


# -- action titles ---------------------------------------------------------


def test_the_reporting_date_is_the_end_of_the_reported_week():
    assert fallback.week_end("2026-W35") == date(2026, 8, 28)
    assert fallback.week_end("2026-W01") == date(2026, 1, 2)


def test_the_roadmap_marks_the_reported_week_not_the_last_milestone(programme):
    spec = fallback.build_deck_spec(programme, "2026-W33")
    roadmap = next(s for s in spec.slides if s.layout == "roadmap_gantt")
    assert roadmap.today == fallback.week_end("2026-W33")


def test_titles_change_when_the_position_changes(programme):
    """An action title that survives the numbers changing is not an action title."""
    wp = programme.work_packages[0]
    week = programme.weeks()[-1]
    before = fallback.charter_title(programme, week, wp)

    payload = programme.model_dump(mode="json")
    for status in payload["weekly_status"]:
        if status["week"] == week:
            status["rag"] = RAG.GREEN.value
    all_green = Programme.model_validate(payload)
    after = fallback.charter_title(all_green, week, wp)

    assert before != after
    assert "on track" in after


def test_the_roadmap_title_names_the_next_gate(programme):
    week = programme.weeks()[-1]
    title = fallback.roadmap_title(programme, week)
    upcoming = min(
        (g for g in programme.stage_gates if g.status.value != "passed"), key=lambda g: g.date
    )
    assert f"Gate {upcoming.number}" in title


def test_titles_stay_inside_the_schema_limit(spec):
    for slide in spec.slides:
        assert len(slide.title) <= 160
