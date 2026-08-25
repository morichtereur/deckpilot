"""The grid helpers are the foundation every layout stands on, so they are tested
for the properties layouts actually rely on: columns never overlap, nothing ever
crosses the outer margin, and gutters are exact."""

import pytest

from deckpilot.theme import tokens as t


def test_slide_is_16_by_9():
    assert t.SLIDE_W == 12192000
    assert t.SLIDE_H == 6858000
    assert round(t.SLIDE_W / t.SLIDE_H, 4) == round(16 / 9, 4)


def test_margins_meet_the_design_minimum():
    minimum = t.inches(0.4)
    assert minimum <= t.MARGIN
    assert t.content_left() >= minimum
    assert t.SLIDE_W - (t.content_left() + t.content_width()) >= minimum


def test_content_band_sits_between_title_and_footer():
    assert t.content_top() > t.MARGIN + t.TITLE_BAND_H
    assert t.content_bottom() < t.footer_top()
    assert t.content_height() > 0
    assert t.content_height() == t.content_bottom() - t.content_top()


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
def test_columns_tile_the_content_width_without_overlap(n):
    w = t.col_w(n)
    xs = [t.col_x(i, n) for i in range(n)]

    assert xs[0] == t.content_left()
    assert xs == sorted(xs)
    for i in range(n - 1):
        gap = xs[i + 1] - (xs[i] + w)
        assert gap == t.GUTTER, f"gutter between columns {i} and {i + 1} is {gap}"

    right = xs[-1] + w
    assert right <= t.content_left() + t.content_width()
    # Integer division may drop sub-EMU remainders, but never more than one per column.
    assert (t.content_left() + t.content_width()) - right <= n


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_rows_tile_the_content_height_without_overlap(n):
    h = t.row_h(n)
    ys = [t.row_y(i, n) for i in range(n)]
    assert ys[0] == t.content_top()
    for i in range(n - 1):
        assert ys[i + 1] - (ys[i] + h) == t.GUTTER
    assert ys[-1] + h <= t.content_bottom() + n


def test_columns_respect_a_custom_region():
    x0, total = t.inches(2.0), t.inches(6.0)
    n = 3
    w = t.col_w(n, total=total)
    xs = [t.col_x(i, n, total=total, x0=x0) for i in range(n)]
    assert xs[0] == x0
    assert xs[-1] + w <= x0 + total
    assert w * n + t.GUTTER * (n - 1) <= total


def test_column_index_out_of_range_is_an_error():
    with pytest.raises(IndexError):
        t.col_x(3, 3)
    with pytest.raises(IndexError):
        t.col_x(-1, 3)
    with pytest.raises(IndexError):
        t.row_y(2, 2)


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_column_count_is_an_error(bad):
    with pytest.raises(ValueError):
        t.col_w(bad)
    with pytest.raises(ValueError):
        t.row_h(bad)


def test_considerations_panel_partitions_the_content_width():
    assert t.body_width_with_panel() + t.GUTTER + t.panel_width() == t.content_width()
    assert t.panel_left() + t.panel_width() == t.content_left() + t.content_width()
    assert t.panel_left() > t.content_left() + t.body_width_with_panel()


def test_panel_takes_about_a_quarter():
    ratio = t.panel_width() / t.content_width()
    assert 0.22 < ratio < 0.28


def test_unit_conversions():
    assert t.inches(1) == 914400
    assert t.points(72) == 914400
    assert t.points(10) == 127000


def test_tint_and_shade_move_toward_white_and_black():
    assert t.tint(t.PRIMARY, 0.0) == t.PRIMARY
    assert t.tint(t.PRIMARY, 1.0) == t.WHITE
    assert t.shade(t.PRIMARY, 1.0) == (0, 0, 0)
    half = t.tint(t.PRIMARY, 0.5)
    assert all(p <= h <= 0xFF for p, h in zip(t.PRIMARY, half, strict=True))
    # Out-of-range amounts clamp rather than producing invalid channels.
    assert t.tint(t.PRIMARY, 5.0) == t.WHITE
    assert t.shade(t.PRIMARY, -1.0) == t.PRIMARY


def test_status_palette_is_complete_and_distinct():
    assert set(t.RAG_COLORS) == {"green", "amber", "red", "neutral"}
    assert len({str(c) for c in t.RAG_COLORS.values()}) == 4
    assert set(t.SEVERITY_COLORS) == {"H", "M", "L"}


def test_type_scale_matches_the_brief():
    assert (t.FS_TITLE, t.FS_SUBTITLE, t.FS_BODY, t.FS_DENSE) == (20, 12, 10, 9)
    assert t.FS_SECTION_NUMBER >= 120
    assert t.FS_MIN_BODY < t.FS_BODY and t.FS_MIN_DENSE < t.FS_DENSE
