"""The overflow guarantee is the renderer's central promise, so the fitting
engine is tested on the properties the layouts depend on: it never returns a
size that does not fit, it converges, and when it truly cannot fit it says so."""

import logging

import pytest

from deckpilot.renderer import text_metrics as tm
from deckpilot.renderer.base import (
    FitRequest,
    TextStyle,
    add_slide,
    add_textbox,
    fit_group,
    fit_text,
    natural_height_pt,
    new_deck,
)
from deckpilot.theme import tokens as T

LOREM = (
    "Standardise the close calendar to a 5+2 day cycle across all five regions and "
    "reduce the journal taxonomy from 214 entry types to 61 before the pilot close."
)


@pytest.fixture
def slide():
    return add_slide(new_deck())


def box(slide, w_in: float, h_in: float):
    return add_textbox(slide, T.inches(1), T.inches(1), T.inches(w_in), T.inches(h_in))


def frame_size_pt(frame) -> float:
    return frame.paragraphs[0].runs[0].font.size.pt


def frame_text(frame) -> str:
    return "\n".join(r.text for p in frame.paragraphs for r in p.runs)


# -- measurement -----------------------------------------------------------


def test_wrap_never_exceeds_the_line_width():
    width = 140.0
    for line in tm.wrap(LOREM, width, 10):
        assert tm.text_width(line, 10) <= width + 0.01


def test_wrap_preserves_the_words():
    assert " ".join(tm.wrap(LOREM, 140, 10)).split() == LOREM.split()


def test_a_word_longer_than_the_line_gets_its_own_line():
    """PowerPoint does not hyphenate; an oversized word overhangs its box."""
    lines = tm.wrap("supercalifragilistic", 20, 10)
    assert lines == ["supercalifragilistic"]
    assert tm.text_width(lines[0], 10) > 20


def test_break_words_splits_only_when_asked():
    lines = tm.wrap("supercalifragilistic", 20, 10, break_words=True)
    assert len(lines) > 1
    assert all(tm.text_width(line, 10) <= 20.01 for line in lines)


def test_fitting_rejects_a_size_whose_longest_word_overhangs(slide):
    """A narrow column must shrink to suit its longest word, not break it."""
    shape = box(slide, 0.85, 1.4)
    fit_text(shape.text_frame, "Process Standardisation", 5, 12, where="wp label")
    size = frame_size_pt(shape.text_frame)
    avail_w = (shape.width - 2 * T.TEXT_INSET) / T.EMU_PER_PT
    assert tm.widest_word("Process Standardisation", size) <= avail_w


def test_smaller_type_needs_fewer_lines():
    assert tm.line_count(LOREM, 140, 8) <= tm.line_count(LOREM, 140, 12)


def test_truncate_respects_the_line_budget():
    for budget in (1, 2, 3):
        out = tm.truncate(LOREM, 140, 10, budget)
        assert tm.line_count(out, 140, 10) <= budget
        assert out.endswith(tm.ELLIPSIS)


def test_truncate_leaves_short_text_alone():
    assert tm.truncate("short", 140, 10, 3) == "short"


def test_block_height_grows_with_paragraph_count():
    one = tm.block_height(["a"], 140, 10, space_after_pt=3)
    three = tm.block_height(["a", "b", "c"], 140, 10, space_after_pt=3)
    assert three > one * 2


# -- fitting ---------------------------------------------------------------


def test_a_comfortable_box_keeps_the_maximum_size(slide):
    shape = box(slide, 4.0, 1.5)
    assert fit_text(shape.text_frame, "Short line", 7, 12, where="t") == 12


def test_a_tight_box_shrinks_rather_than_overflowing(slide):
    shape = box(slide, 2.0, 0.6)
    size = fit_text(shape.text_frame, LOREM, 6, 14, where="t")
    assert 6 <= size < 14
    # Whatever size was chosen must actually fit.
    avail_w = (shape.width - 2 * T.TEXT_INSET) / T.EMU_PER_PT
    avail_h = (shape.height - 2 * T.TEXT_INSET) / T.EMU_PER_PT
    assert tm.block_height([LOREM], avail_w, size, line_spacing=T.LINE_SPACING) <= avail_h


def test_the_search_lands_on_the_largest_size_that_fits(slide):
    shape = box(slide, 2.0, 0.6)
    size = fit_text(shape.text_frame, LOREM, 6, 14, where="t")
    avail_w = (shape.width - 2 * T.TEXT_INSET) / T.EMU_PER_PT
    avail_h = (shape.height - 2 * T.TEXT_INSET) / T.EMU_PER_PT
    bigger = size + 0.5
    assert tm.block_height([LOREM], avail_w, bigger, line_spacing=T.LINE_SPACING) > avail_h


def test_sizes_land_on_half_points(slide):
    for h in (0.4, 0.5, 0.7, 0.9, 1.2):
        shape = box(slide, 2.0, h)
        size = fit_text(shape.text_frame, LOREM, 6, 14, where="t")
        assert size * 2 == int(size * 2), size


def test_impossible_content_is_truncated_and_reported(slide, caplog):
    shape = box(slide, 1.0, 0.25)
    with caplog.at_level(logging.WARNING, logger="deckpilot.renderer"):
        size = fit_text(shape.text_frame, LOREM * 3, 7, 10, where="page 4/charter cell")
    assert size == 7
    assert tm.ELLIPSIS in frame_text(shape.text_frame)
    assert "page 4/charter cell" in caplog.text
    assert "truncated" in caplog.text


def test_a_deck_that_fits_logs_nothing(slide, caplog):
    with caplog.at_level(logging.WARNING, logger="deckpilot.renderer"):
        fit_text(box(slide, 4.0, 1.5).text_frame, "Comfortable", 7, 12, where="t")
    assert caplog.text == ""


def test_empty_content_is_accepted(slide):
    shape = box(slide, 2.0, 1.0)
    fit_text(shape.text_frame, [], 7, 12, where="t")
    assert frame_text(shape.text_frame) == ""


def test_rotated_frames_measure_against_swapped_extents(slide):
    """A vertical label's usable width is its box's height."""
    shape = box(slide, 0.4, 3.0)
    size = fit_text(
        shape.text_frame, "Key activities", 6, 10, where="t",
        style=TextStyle(wrap=False), shape_w=T.inches(3.0), shape_h=T.inches(0.4),
    )
    assert size == 10


def test_no_wrap_shrinks_instead_of_wrapping(slide):
    shape = box(slide, 1.1, 1.0)
    fit_text(shape.text_frame, "Key activities", 5, 12, where="t", style=TextStyle(wrap=False))
    assert shape.text_frame.word_wrap is False
    assert len(shape.text_frame.paragraphs) == 1


# -- group fitting ---------------------------------------------------------


def _requests(slide, texts, w_in=2.0, h_in=1.0):
    out = []
    for i, text in enumerate(texts):
        shape = add_textbox(
            slide, T.inches(1 + i * 2.2), T.inches(1), T.inches(w_in), T.inches(h_in)
        )
        out.append(
            FitRequest(
                shape.text_frame, [text], shape.width, shape.height, TextStyle(), f"cell {i}"
            )
        )
    return out


def test_peer_boxes_all_get_the_same_size(slide):
    reqs = _requests(slide, ["Short", LOREM, "Medium length header"])
    size = fit_group(reqs, 6, 12)
    for req in reqs:
        assert frame_size_pt(req.frame) == size


def test_the_group_size_is_set_by_the_tightest_member(slide):
    alone = fit_text(box(slide, 2.0, 1.0).text_frame, "Short", 6, 12, where="t")
    grouped = fit_group(_requests(slide, ["Short", LOREM * 2]), 6, 12)
    assert grouped < alone


def test_group_fitting_of_empty_requests_is_harmless(slide):
    reqs = _requests(slide, ["x"])
    reqs[0] = FitRequest(reqs[0].frame, [], reqs[0].width, reqs[0].height, TextStyle(), "empty")
    assert fit_group(reqs, 6, 12) == 12


def test_fill_opens_the_bullet_gaps_without_changing_the_size(slide):
    items = ["First bullet", "Second bullet", "Third bullet"]

    def build():
        shape = add_textbox(slide, T.inches(1), T.inches(1), T.inches(2.4), T.inches(2.6))
        return FitRequest(
            shape.text_frame, items, shape.width, shape.height,
            TextStyle(bullet="•"), "cell",
        )

    plain, filled = build(), build()
    assert fit_group([plain], 7, 10) == fit_group([filled], 7, 10, fill=True)
    gap_plain = plain.frame.paragraphs[0].space_after
    gap_filled = filled.frame.paragraphs[0].space_after
    assert gap_filled > gap_plain


def test_natural_height_tracks_content(slide):
    style = TextStyle(bullet="•")
    one = natural_height_pt(["Only one bullet"], T.inches(2.4), 10, style)
    many = natural_height_pt(["Only one bullet"] * 4, T.inches(2.4), 10, style)
    assert many > one
