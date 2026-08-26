"""Every layout must produce a slide that passes the geometry checks the visual
QA loop would otherwise have to catch by eye."""

import logging

import pytest

from deckpilot.renderer import section_divider, workstream_charter
from deckpilot.renderer.base import new_deck
from deckpilot.renderer.qa import check_slide
from deckpilot.specgen.samples import SAMPLES
from deckpilot.specgen.schema import CharterColumn
from deckpilot.theme import tokens as T


def errors(slide, index=1):
    return [f for f in check_slide(index, slide) if f.severity == "error"]


def rendered(spec, page=1):
    prs = new_deck()
    if spec.layout == "section_divider":
        return section_divider.render(prs, spec)
    return workstream_charter.render(prs, spec, page=page)


# -- section divider -------------------------------------------------------


def test_section_divider_is_geometrically_clean():
    assert errors(rendered(SAMPLES["section_divider"])) == []


def test_section_divider_has_no_body_content_and_no_footer():
    slide = rendered(SAMPLES["section_divider"])
    names = {s.name for s in slide.shapes}
    assert not any(n.startswith("footer:") for n in names)
    assert names == {"bleed:background", "bleed:accent", "section:number",
                     "section:title", "section:kicker"}


def test_section_divider_bleeds_to_every_edge():
    slide = rendered(SAMPLES["section_divider"])
    bg = next(s for s in slide.shapes if s.name == "bleed:background")
    assert (bg.left, bg.top) == (0, 0)
    assert (bg.width, bg.height) == (T.SLIDE_W, T.SLIDE_H)


def test_section_number_is_set_oversized():
    slide = rendered(SAMPLES["section_divider"])
    number = next(s for s in slide.shapes if s.name == "section:number")
    assert number.text_frame.paragraphs[0].runs[0].font.size.pt >= 120


# -- workstream charter ----------------------------------------------------


@pytest.mark.parametrize("n", [3, 4, 5])
def test_charter_is_clean_at_every_supported_column_count(n):
    base = SAMPLES["workstream_charter"]
    columns = [
        CharterColumn(
            number=f"2.{i + 1}",
            name=base.columns[i % len(base.columns)].name,
            activities=base.columns[i % len(base.columns)].activities,
            outcomes=base.columns[i % len(base.columns)].outcomes,
        )
        for i in range(n)
    ]
    spec = base.model_copy(update={"columns": columns})
    assert errors(rendered(spec)) == []


def test_charter_columns_share_one_header_size():
    slide = rendered(SAMPLES["workstream_charter"])
    sizes = {
        s.text_frame.paragraphs[0].runs[0].font.size.pt
        for s in slide.shapes
        if s.name.endswith(":name")
    }
    assert len(sizes) == 1


def test_charter_cells_in_a_band_share_one_size():
    slide = rendered(SAMPLES["workstream_charter"])
    for band in ("act:text", "out:text"):
        sizes = {
            s.text_frame.paragraphs[0].runs[0].font.size.pt
            for s in slide.shapes
            if s.name.endswith(band)
        }
        assert len(sizes) == 1, band


def test_charter_bullets_stay_in_the_dense_range():
    slide = rendered(SAMPLES["workstream_charter"])
    sizes = [
        s.text_frame.paragraphs[0].runs[0].font.size.pt
        for s in slide.shapes
        if s.name.endswith("act:text")
    ]
    assert all(T.FS_MIN_DENSE <= size <= T.FS_DENSE + 1 for size in sizes)


def test_charter_without_considerations_uses_the_full_width():
    spec = SAMPLES["workstream_charter"].model_copy(update={"considerations": []})
    slide = rendered(spec)
    assert not any(s.name.startswith("panel:") for s in slide.shapes)
    right = max(s.left + s.width for s in slide.shapes if not s.name.startswith("footer:"))
    assert right > T.panel_left()


def test_charter_with_considerations_leaves_room_for_the_panel():
    slide = rendered(SAMPLES["workstream_charter"])
    assert any(s.name == "panel:bg" for s in slide.shapes)
    body = [
        s for s in slide.shapes
        if not s.name.startswith(("panel:", "footer:", "title:"))
    ]
    assert max(s.left + s.width for s in body) <= T.panel_left()


def test_charter_carries_a_footer_with_the_page_number():
    slide = rendered(SAMPLES["workstream_charter"], page=7)
    page = next(s for s in slide.shapes if s.name == "footer:page")
    assert page.text_frame.paragraphs[0].runs[0].text == "7"


def test_charter_content_is_native_text_not_images():
    slide = rendered(SAMPLES["workstream_charter"])
    assert not any(s.shape_type == 13 for s in slide.shapes)  # 13 = PICTURE
    assert any(s.has_text_frame and s.text_frame.text for s in slide.shapes)


def test_charter_survives_content_that_cannot_fit(caplog):
    """Overlong content must be reported, not silently spilled over the grid."""
    base = SAMPLES["workstream_charter"]
    fat = base.model_copy(
        update={
            "columns": [
                c.model_copy(update={"activities": [a * 6 for a in c.activities]})
                for c in base.columns
            ]
        }
    )
    with caplog.at_level(logging.WARNING, logger="deckpilot.renderer"):
        slide = rendered(fat)
    assert errors(slide) == []
    assert "truncated" in caplog.text


# -- roadmap gantt ---------------------------------------------------------


def test_roadmap_is_geometrically_clean():
    from deckpilot.renderer import roadmap_gantt

    prs = new_deck()
    slide = roadmap_gantt.render(prs, SAMPLES["roadmap_gantt"], page=3)
    assert errors(slide, 3) == []


def test_roadmap_bars_stay_inside_the_grid():
    from deckpilot.renderer import roadmap_gantt
    from deckpilot.renderer.timeline import MonthGrid

    spec = SAMPLES["roadmap_gantt"]
    prs = new_deck()
    slide = roadmap_gantt.render(prs, spec, page=3)

    grid_x = T.content_left() + T.GANTT_WP_COL_W + T.GANTT_SS_COL_W
    grid_w = T.body_width_with_panel() - T.GANTT_WP_COL_W - T.GANTT_SS_COL_W
    grid = MonthGrid(spec.window_start, spec.window_end, grid_x, grid_w)

    bars = [s for s in slide.shapes if ":bar" in s.name]
    assert bars
    for bar in bars:
        assert bar.left >= grid.x
        assert bar.left + bar.width <= grid.right + 1


def test_roadmap_stacks_phases_that_run_in_parallel():
    """The migration row has overlapping waves and must not draw them on one line."""
    from deckpilot.renderer import roadmap_gantt

    spec = SAMPLES["roadmap_gantt"]
    row_index = next(
        i for i, r in enumerate(spec.rows) if r.sub_stream.startswith("Knowledge Transfer")
    )
    prs = new_deck()
    slide = roadmap_gantt.render(prs, spec, page=3)
    tops = {s.top for s in slide.shapes if s.name.startswith(f"row{row_index}:bar")}
    assert len(tops) > 1


def test_roadmap_marks_the_reporting_date_once():
    from deckpilot.renderer import roadmap_gantt

    prs = new_deck()
    slide = roadmap_gantt.render(prs, SAMPLES["roadmap_gantt"], page=3)
    # Month rules are hairlines; the reporting date is the one heavier vertical.
    verticals = [
        s for s in slide.shapes
        if s.shape_type == 9 and s.width == 0 and s.height > T.inches(1)  # 9 = LINE
    ]
    assert len(verticals) > 1, "expected month rules as well"
    heavy = [s for s in verticals if s.line.width.pt > T.HAIRLINE_PT]
    assert len(heavy) == 1
    assert heavy[0].line.color.rgb == T.SECONDARY


def test_roadmap_drops_bars_outside_the_window():
    from datetime import date

    from deckpilot.renderer import roadmap_gantt

    spec = SAMPLES["roadmap_gantt"].model_copy(
        update={"window_start": date(2026, 6, 1), "window_end": date(2026, 9, 30)}
    )
    prs = new_deck()
    slide = roadmap_gantt.render(prs, spec, page=3)
    assert errors(slide, 3) == []


# -- governance chart ------------------------------------------------------


def test_governance_chart_is_geometrically_clean():
    from deckpilot.renderer import governance_chart

    prs = new_deck()
    slide = governance_chart.render(prs, SAMPLES["governance_chart"], page=4)
    assert errors(slide, 4) == []


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_governance_chart_is_clean_at_every_supported_unit_count(n):
    from deckpilot.renderer import governance_chart

    base = SAMPLES["governance_chart"]
    units = [base.units[i % len(base.units)] for i in range(n)]
    spec = base.model_copy(update={"units": units})
    prs = new_deck()
    assert errors(governance_chart.render(prs, spec, page=4), 4) == []


def test_governance_tiers_are_connected_by_native_lines():
    from deckpilot.renderer import governance_chart

    prs = new_deck()
    slide = governance_chart.render(prs, SAMPLES["governance_chart"], page=4)
    lines = [s for s in slide.shapes if s.shape_type == 9]  # 9 = LINE
    # Two drops from the tiers, one distribution bus, one drop per unit.
    assert len(lines) == 3 + len(SAMPLES["governance_chart"].units)
    assert all(s.line.color.rgb == T.SECONDARY for s in lines)


def test_governance_units_hang_below_the_management_box():
    from deckpilot.renderer import governance_chart

    prs = new_deck()
    slide = governance_chart.render(prs, SAMPLES["governance_chart"], page=4)
    mgmt = next(s for s in slide.shapes if s.name == "pmo:box")
    units = [s for s in slide.shapes if s.name.endswith(":box") and s.name.startswith("unit")]
    assert units
    assert all(u.top > mgmt.top + mgmt.height for u in units)


def test_governance_tiers_share_one_member_size():
    from deckpilot.renderer import governance_chart

    prs = new_deck()
    slide = governance_chart.render(prs, SAMPLES["governance_chart"], page=4)
    sizes = {
        s.text_frame.paragraphs[0].runs[0].font.size.pt
        for s in slide.shapes
        if ":members" in s.name
    }
    assert len(sizes) == 1


def test_governance_comments_panel_is_labelled_comments():
    from deckpilot.renderer import governance_chart

    prs = new_deck()
    slide = governance_chart.render(prs, SAMPLES["governance_chart"], page=4)
    heading = next(s for s in slide.shapes if s.name == "panel:heading")
    assert heading.text_frame.paragraphs[0].runs[0].text == "Comments"
