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
