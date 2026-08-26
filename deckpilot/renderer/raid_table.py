"""RAID log as a real PowerPoint table, grouped by type.

A native table rather than a grid of drawn rectangles: a reader who wants to add
a row, re-sort, or paste the log into a tracker should be able to. Severity is
carried by a filled cell rather than a separate chip shape, for the same reason -
one object, still coloured, still editable.
"""

from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.presentation import Presentation as PresentationType
from pptx.slide import Slide
from pptx.util import Emu, Pt

from deckpilot.renderer import text_metrics as tm
from deckpilot.renderer.base import (
    _drop_theme_style,
    add_slide,
    footer,
    title_block,
)
from deckpilot.specgen.schema import RaidRow, RaidTableSpec
from deckpilot.theme import tokens as T

# Column widths as fractions of the content width. They sum to 1.
COLUMN_SHARE = {
    "severity": 0.045,
    "id": 0.052,
    "title": 0.300,
    "owner": 0.130,
    "due": 0.078,
    "mitigation": 0.395,
}
HEADINGS = ["", "ID", "Item", "Owner", "Due", "Mitigation and next step"]
GROUP_ORDER = ["risk", "issue", "dependency", "assumption"]


def _ordered(rows: list[RaidRow]) -> list[tuple[str, list[RaidRow]]]:
    groups = []
    for kind in GROUP_ORDER:
        members = [r for r in rows if r.kind == kind]
        if members:
            groups.append((kind, members))
    return groups


def _cell(cell, text: str, size: float, *, bold=False, color=None, align=PP_ALIGN.LEFT,
          fill=None) -> None:
    cell.margin_left = cell.margin_right = Emu(T.RAID_CELL_PAD)
    cell.margin_top = cell.margin_bottom = Emu(CELL_MARGIN)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    if fill is None:
        cell.fill.background()
    else:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill

    frame = cell.text_frame
    frame.word_wrap = True
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = T.FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color if color is not None else T.GRAY_DARK


CELL_MARGIN = T.inches(0.03)


def _row_lines(row: RaidRow, widths: dict[str, int], size: float) -> int:
    """How many lines the tallest cell in this row needs."""
    return max(
        tm.line_count(text, (widths[key] - 2 * T.RAID_CELL_PAD) / T.EMU_PER_PT, size)
        for key, text in (
            ("title", row.title),
            ("mitigation", row.mitigation),
            ("owner", row.owner),
        )
    )


def _plan(rows: list[RaidRow], widths: dict[str, int], groups: int,
          available: int) -> tuple[float, list[int]]:
    """Choose a type size and a height for every row so the whole table fits.

    A row height set on a python-pptx table is a minimum, not a maximum: if a
    cell wraps to more lines than the height allows, PowerPoint grows the row and
    the table runs off the bottom of the slide. So the heights have to be
    computed from the wrapped line count rather than divided out evenly.
    """
    fixed = T.RAID_HEADER_H + groups * T.RAID_GROUP_H
    candidates = [T.FS_DENSE, T.FS_DENSE - 0.5, T.FS_MICRO, T.FS_MICRO - 0.5, T.FS_MICRO - 1]
    heights: list[int] = []
    for size in candidates:
        line_h = size * tm.LINE_HEIGHT_FACTOR * T.EMU_PER_PT
        heights = [
            max(T.RAID_ROW_MIN_H, int(_row_lines(row, widths, size) * line_h) + 2 * CELL_MARGIN)
            for row in rows
        ]
        if fixed + sum(heights) <= available:
            return size, heights
    return candidates[-1], heights


def render(prs: PresentationType, spec: RaidTableSpec, page: int) -> Slide:
    slide = add_slide(prs)
    title_block(slide, spec.title, spec.subtitle, where=f"page {page}")

    groups = _ordered(spec.rows)
    total_rows = 1 + sum(1 + len(members) for _, members in groups)

    left, top = T.content_left(), T.content_top()
    width, height = T.content_width(), T.content_height()

    graphic = slide.shapes.add_table(total_rows, len(HEADINGS), Emu(left), Emu(top),
                                     Emu(width), Emu(height))
    graphic.name = "raid:table"
    table = graphic.table
    # python-pptx applies a banded theme style; every fill here is set explicitly.
    table.first_row = False
    table.horz_banding = False
    _drop_theme_style(graphic)

    widths = {}
    for i, key in enumerate(COLUMN_SHARE):
        widths[key] = int(width * COLUMN_SHARE[key])
        table.columns[i].width = Emu(widths[key])

    size, row_heights = _plan(spec.rows, widths, len(groups), height)
    # The frame is sized to what the rows actually need, so the geometry check
    # sees the same table the renderer will draw.
    graphic.height = Emu(T.RAID_HEADER_H + len(groups) * T.RAID_GROUP_H + sum(row_heights))

    table.rows[0].height = Emu(T.RAID_HEADER_H)
    for i, heading in enumerate(HEADINGS):
        _cell(table.cell(0, i), heading, T.FS_MICRO, bold=True, color=T.WHITE, fill=T.PRIMARY)

    index = 1
    for kind, members in groups:
        table.rows[index].height = Emu(T.RAID_GROUP_H)
        label = spec.group_labels.get(kind, kind.title())
        _cell(table.cell(index, 0), "", T.FS_MICRO, fill=T.tint(T.PRIMARY, 0.86))
        _cell(table.cell(index, 1), f"{label} ({len(members)})", T.FS_MICRO,
              bold=True, color=T.PRIMARY, fill=T.tint(T.PRIMARY, 0.86))
        table.cell(index, 1).merge(table.cell(index, len(HEADINGS) - 1))
        index += 1

        for row in members:
            table.rows[index].height = Emu(row_heights[spec.rows.index(row)])
            tint = T.WHITE if index % 2 else T.ROW_TINT
            severity_fill = T.SEVERITY_COLORS[row.severity]
            _cell(table.cell(index, 0), row.severity, size, bold=True,
                  color=T.on_color(severity_fill), align=PP_ALIGN.CENTER, fill=severity_fill)
            for column, text, align in (
                (1, row.id, PP_ALIGN.LEFT),
                (2, row.title, PP_ALIGN.LEFT),
                (3, row.owner, PP_ALIGN.LEFT),
                (4, row.due, PP_ALIGN.LEFT),
                (5, row.mitigation, PP_ALIGN.LEFT),
            ):
                _cell(table.cell(index, column), text, size, align=align, fill=tint)
            index += 1

    footer(slide, page)
    return slide
