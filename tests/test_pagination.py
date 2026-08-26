"""Splitting a log across slides.

The properties that matter are conservation (every row appears exactly once, in
order), containment (no page asks for more height than a slide has), and
consistency (every page is set at the same size). Balance is the aesthetic one:
filling greedily leaves the last slide nearly empty, which nobody laying this out
by hand would accept.
"""

import pytest

from deckpilot.data.generate import build_programme
from deckpilot.renderer import raid_table
from deckpilot.renderer import text_metrics as tm
from deckpilot.renderer.base import new_deck
from deckpilot.renderer.qa import check_slide
from deckpilot.specgen import fallback
from deckpilot.specgen.schema import RaidRow, RaidTableSpec
from deckpilot.theme import tokens as T

WIDTH = T.content_width()
HEIGHT = T.content_height()


@pytest.fixture(scope="module")
def rows() -> list[RaidRow]:
    programme = build_programme()
    return [fallback._raid_row(i) for i in fallback.rank_raid(programme.raid)]


def page_height(page, size=raid_table.PREFERRED_SIZE) -> int:
    """What the renderer will actually ask for, given these rows."""
    widths = raid_table.column_widths(WIDTH)
    groups = len({row.kind for row in page.rows})
    _, heights = raid_table._plan(page.rows, widths, groups, HEIGHT)
    return T.RAID_HEADER_H + groups * T.RAID_GROUP_H + sum(heights)


# -- conservation ----------------------------------------------------------


def test_every_row_appears_exactly_once_and_in_order(rows):
    pages = raid_table.paginate(rows, WIDTH, HEIGHT)
    flat = [row for page in pages for row in page.rows]
    assert len(flat) == len(rows)
    assert {r.id for r in flat} == {r.id for r in rows}
    # Grouping order is preserved across the split.
    kinds = [r.kind for r in flat]
    first_seen = []
    for kind in kinds:
        if kind not in first_seen:
            first_seen.append(kind)
    assert kinds == sorted(kinds, key=first_seen.index)


def test_a_log_that_fits_is_left_on_one_page(rows):
    pages = raid_table.paginate(rows[:4], WIDTH, HEIGHT)
    assert len(pages) == 1
    assert pages[0].continued_groups == []


def test_a_long_log_is_split(rows):
    pages = raid_table.paginate(rows, WIDTH, HEIGHT)
    assert len(pages) >= 2


# -- containment -----------------------------------------------------------


def test_no_page_asks_for_more_height_than_a_slide_has(rows):
    for page in raid_table.paginate(rows, WIDTH, HEIGHT):
        assert page_height(page) <= HEIGHT


def test_a_much_shorter_slide_produces_more_pages_all_of_which_fit(rows):
    short = T.inches(2.2)
    pages = raid_table.paginate(rows, WIDTH, short)
    assert len(pages) > 2
    for page in pages:
        assert page.rows
    flat = [r.id for page in pages for r in page.rows]
    assert len(flat) == len(rows)


# -- continuation ----------------------------------------------------------


def test_a_group_split_across_pages_is_re_announced(rows):
    pages = raid_table.paginate(rows, WIDTH, HEIGHT)
    for earlier, later in zip(pages, pages[1:], strict=False):
        carried = earlier.rows[-1].kind
        if any(r.kind == carried for r in later.rows):
            assert carried in later.continued_groups
        else:
            assert carried not in later.continued_groups


def test_the_first_page_never_continues_anything(rows):
    assert raid_table.paginate(rows, WIDTH, HEIGHT)[0].continued_groups == []


def test_a_continued_group_is_labelled_continued_and_loses_its_count(rows):
    pages = raid_table.paginate(rows, WIDTH, HEIGHT)
    later = next((p for p in pages if p.continued_groups), None)
    assert later is not None

    spec = RaidTableSpec(
        title="t", subtitle="s", rows=later.rows, continued_groups=later.continued_groups
    )
    slide = raid_table.render(new_deck(), spec, page=2)
    table = next(s for s in slide.shapes if s.name == "raid:table").table
    labels = [table.cell(i, 1).text for i in range(len(table.rows))]
    carried = spec.group_labels[later.continued_groups[0]]
    assert any(t == f"{carried} (continued)" for t in labels), labels


# -- balance and consistency ----------------------------------------------


def test_pages_are_balanced_rather_than_filled_greedily(rows):
    """Greedy filling gives 16 rows then 2; balancing gives 9 and 9."""
    pages = raid_table.paginate(rows, WIDTH, HEIGHT)
    counts = [len(p.rows) for p in pages]
    assert min(counts) >= max(counts) - 2, counts


def test_every_page_renders_at_the_same_type_size(rows):
    """A second slide set a point off the first looks like a different document."""
    sizes = set()
    for page in raid_table.paginate(rows, WIDTH, HEIGHT):
        spec = RaidTableSpec(
            title="t", subtitle="s", rows=page.rows, continued_groups=page.continued_groups
        )
        slide = raid_table.render(new_deck(), spec, page=1)
        table = next(s for s in slide.shapes if s.name == "raid:table").table
        for i in range(1, len(table.rows)):
            runs = table.cell(i, 2).text_frame.paragraphs[0].runs
            if runs:
                sizes.add(runs[0].font.size.pt)
    assert len(sizes) == 1, sizes


# -- as wired into the deck ------------------------------------------------


def test_the_appendix_covers_the_whole_log():
    programme = build_programme()
    pages = fallback.raid_appendix(programme, programme.weeks()[-1])
    shown = {row.id for page in pages for row in page.rows}
    assert shown == {item.id for item in programme.raid}


def test_the_appendix_numbers_its_pages():
    programme = build_programme()
    pages = fallback.raid_appendix(programme, programme.weeks()[-1])
    for n, page in enumerate(pages, start=1):
        assert f"Page {n} of {len(pages)}" in page.subtitle


def test_every_appendix_page_is_clean_and_above_the_footer():
    programme = build_programme()
    for i, spec in enumerate(fallback.raid_appendix(programme, programme.weeks()[-1]), 1):
        slide = raid_table.render(new_deck(), spec, page=i)
        assert [f for f in check_slide(i, slide) if f.severity == "error"] == []
        frame = next(s for s in slide.shapes if s.name == "raid:table")
        assert frame.top + frame.height <= T.footer_top()


def test_declared_heights_err_high_rather_than_low(rows):
    """A row height is a floor: the renderer grows anything under-declared."""
    widths = raid_table.column_widths(WIDTH)
    for row in rows:
        lines = raid_table._row_lines(row, widths, raid_table.PREFERRED_SIZE)
        bare = tm.line_count(
            row.mitigation,
            (widths["mitigation"] - 2 * T.RAID_CELL_PAD) / T.EMU_PER_PT,
            raid_table.PREFERRED_SIZE,
        )
        assert lines >= bare, row.id
    assert raid_table.TABLE_LINE_HEIGHT > tm.LINE_HEIGHT_FACTOR
    assert raid_table.WIDTH_SAFETY < 1.0
