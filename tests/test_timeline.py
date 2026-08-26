"""Roadmap date maths.

Everything here is about edges: bars that start before the window or end after
it, a milestone on the last day, a task too short to see. Those are the cases
that produce a bar hanging off the grid, and they are far easier to pin down as
arithmetic than by looking at a slide.
"""

from datetime import date

import pytest

from deckpilot.renderer.timeline import MonthGrid, assign_lanes, months_between

X, W = 1_000_000, 12_000_000
START, END = date(2026, 2, 2), date(2027, 1, 29)


@pytest.fixture
def grid() -> MonthGrid:
    return MonthGrid(START, END, X, W)


# -- month enumeration -----------------------------------------------------


def test_months_between_is_inclusive_at_both_ends():
    months = months_between(date(2026, 2, 10), date(2026, 4, 1))
    assert months == [(2026, 2), (2026, 3), (2026, 4)]


def test_months_between_crosses_the_year():
    months = months_between(date(2026, 11, 30), date(2027, 2, 1))
    assert months == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]


def test_a_single_month_window_is_one_column():
    assert months_between(date(2026, 3, 4), date(2026, 3, 30)) == [(2026, 3)]


def test_a_backwards_window_is_an_error():
    with pytest.raises(ValueError, match="before it starts"):
        months_between(date(2026, 5, 1), date(2026, 4, 1))


def test_the_sample_window_is_within_the_brief_range(grid):
    assert 9 <= grid.month_count <= 14


def test_month_width_divides_the_grid(grid):
    assert grid.month_width * grid.month_count == pytest.approx(W)


def test_january_and_the_first_month_carry_the_year(grid):
    labels = grid.labels()
    assert labels[0] == "Feb 26"
    assert labels[-1] == "Jan 27"
    assert labels[1] == "Mar"


# -- positioning -----------------------------------------------------------


def test_positions_increase_with_time(grid):
    days = [date(2026, 2, 2), date(2026, 6, 15), date(2026, 11, 1), date(2027, 1, 20)]
    xs = [grid.position(d) for d in days]
    assert xs == sorted(xs)


def test_the_first_of_the_first_month_sits_on_the_left_edge(grid):
    assert grid.position(date(2026, 2, 1)) == pytest.approx(X)


def test_month_boundaries_line_up_with_the_column_edges(grid):
    for i, (year, month) in enumerate(grid.months):
        assert grid.position(date(year, month, 1)) == pytest.approx(grid.month_x(i))


def test_dates_outside_the_window_clamp_to_the_edges(grid):
    assert grid.position(date(2025, 6, 1)) < X
    assert grid.clamped(date(2025, 6, 1)) == X
    assert grid.position(date(2028, 1, 1)) > grid.right
    assert grid.clamped(date(2028, 1, 1)) == grid.right


def test_visibility_matches_the_window(grid):
    assert grid.is_visible(START) and grid.is_visible(END)
    assert not grid.is_visible(date(2026, 2, 1))
    assert not grid.is_visible(date(2027, 1, 30))


def test_a_zero_width_grid_is_an_error():
    with pytest.raises(ValueError, match="width must be positive"):
        MonthGrid(START, END, X, 0)


# -- bars ------------------------------------------------------------------


def test_a_bar_inside_the_window_is_not_clipped(grid):
    x, w = grid.bar(date(2026, 3, 1), date(2026, 5, 31))
    assert x == pytest.approx(grid.month_x(1), abs=2)
    assert x + w == pytest.approx(grid.month_x(4), abs=2)


def test_a_bar_starting_before_the_window_is_cut_at_the_left_edge(grid):
    x, w = grid.bar(date(2025, 1, 1), date(2026, 3, 31))
    assert x == X
    assert x + w == pytest.approx(grid.month_x(2), abs=2)


def test_a_bar_ending_after_the_window_is_cut_at_the_right_edge(grid):
    x, w = grid.bar(date(2026, 12, 1), date(2028, 1, 1))
    assert x + w == grid.right
    assert x == pytest.approx(grid.month_x(10), abs=2)


def test_a_bar_spanning_the_whole_window_fills_the_grid(grid):
    x, w = grid.bar(date(2020, 1, 1), date(2030, 1, 1))
    assert (x, x + w) == (X, grid.right)


def test_a_bar_entirely_outside_the_window_is_dropped(grid):
    assert grid.bar(date(2024, 1, 1), date(2024, 2, 1)) is None
    assert grid.bar(date(2029, 1, 1), date(2029, 2, 1)) is None


def test_a_bar_ending_on_the_window_start_still_shows(grid):
    """An inclusive end date means the bar covers that whole day."""
    extent = grid.bar(date(2025, 12, 1), START)
    assert extent is not None
    assert extent[1] > 0


def test_a_one_day_bar_stays_visible(grid):
    _, w = grid.bar(date(2026, 6, 10), date(2026, 6, 10), min_width=50_000)
    assert w >= 50_000


def test_a_widened_bar_never_escapes_the_right_edge(grid):
    x, w = grid.bar(END, END, min_width=500_000)
    assert w == 500_000
    assert x + w <= grid.right
    assert x >= grid.x


def test_every_bar_stays_within_the_grid(grid):
    spans = [
        (date(2025, 1, 1), date(2025, 6, 1)),
        (date(2025, 1, 1), date(2026, 4, 1)),
        (date(2026, 4, 1), date(2026, 9, 1)),
        (date(2026, 9, 1), date(2028, 1, 1)),
        (date(2027, 3, 1), date(2027, 6, 1)),
        (END, END),
    ]
    for start, end in spans:
        extent = grid.bar(start, end, min_width=40_000)
        if extent is None:
            continue
        x, w = extent
        assert x >= grid.x
        assert x + w <= grid.right


def test_a_backwards_bar_is_an_error(grid):
    with pytest.raises(ValueError, match="before it starts"):
        grid.bar(date(2026, 6, 1), date(2026, 5, 1))


# -- lane packing ----------------------------------------------------------


def test_sequential_spans_share_one_lane():
    spans = [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 2, 2), date(2026, 3, 1)),
        (date(2026, 3, 2), date(2026, 4, 1)),
    ]
    lanes, count = assign_lanes(spans)
    assert count == 1
    assert lanes == [0, 0, 0]


def test_overlapping_spans_get_their_own_lanes():
    spans = [
        (date(2026, 1, 1), date(2026, 4, 1)),
        (date(2026, 3, 1), date(2026, 6, 1)),
    ]
    lanes, count = assign_lanes(spans)
    assert count == 2
    assert lanes[0] != lanes[1]


def test_a_lane_is_reused_once_it_is_free():
    """The migration waves: 1 and 2 overlap, 3 starts after 1 ends."""
    spans = [
        (date(2026, 7, 27), date(2026, 10, 30)),
        (date(2026, 10, 5), date(2026, 12, 18)),
        (date(2026, 11, 30), date(2027, 1, 29)),
    ]
    lanes, count = assign_lanes(spans)
    assert count == 2
    assert lanes[0] == lanes[2]
    assert lanes[1] != lanes[0]


def test_lanes_never_hold_two_overlapping_spans():
    spans = [
        (date(2026, 1, 1), date(2026, 5, 1)),
        (date(2026, 2, 1), date(2026, 6, 1)),
        (date(2026, 3, 1), date(2026, 7, 1)),
        (date(2026, 8, 1), date(2026, 9, 1)),
    ]
    lanes, count = assign_lanes(spans)
    for lane in range(count):
        members = sorted(
            (spans[i] for i in range(len(spans)) if lanes[i] == lane), key=lambda s: s[0]
        )
        for earlier, later in zip(members, members[1:], strict=False):
            assert earlier[1] < later[0]


def test_no_spans_still_reports_one_lane():
    assert assign_lanes([]) == ([], 1)
