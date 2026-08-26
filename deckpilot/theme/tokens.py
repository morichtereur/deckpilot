"""Design tokens: the single source of truth for every colour, size and position.

Renderer modules must not contain literal geometry. If a layout needs a number,
it either comes from a constant here or from one of the grid helpers below.

All geometry is expressed in EMU (English Metric Units), python-pptx's native
unit. 914400 EMU == 1 inch == 72 pt.
"""

from __future__ import annotations

from pptx.dml.color import RGBColor

# --------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------

EMU_PER_INCH = 914400
EMU_PER_PT = 12700


def inches(value: float) -> int:
    """Inches -> EMU."""
    return int(round(value * EMU_PER_INCH))


def points(value: float) -> int:
    """Points -> EMU."""
    return int(round(value * EMU_PER_PT))


# --------------------------------------------------------------------------
# Palette
#
# Deliberately not corporate blue. The primary is a deep ink-plum; the
# secondary is a lighter tint of the same hue. Keeping both in one hue family
# leaves red / amber / green free to carry status meaning exclusively, so a
# RAG chip is never mistaken for decoration.
# --------------------------------------------------------------------------

PRIMARY = RGBColor(0x33, 0x27, 0x4A)  # ink plum - dividers, headers, title band
SECONDARY = RGBColor(0x6E, 0x5B, 0x8E)  # muted violet - badges, accents, neutral bars

STATUS_GREEN = RGBColor(0x1F, 0x8A, 0x5B)
STATUS_AMBER = RGBColor(0xD8, 0x9A, 0x1E)
STATUS_RED = RGBColor(0xB2, 0x3A, 0x2F)
STATUS_NEUTRAL = RGBColor(0x8A, 0x8F, 0x98)  # not started / not applicable

GRAY_DARK = RGBColor(0x2B, 0x2E, 0x33)  # body text
GRAY_LIGHT = RGBColor(0xE4, 0xE6, 0xEA)  # rules, table borders, empty track fills

WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def tint(color: RGBColor, amount: float) -> RGBColor:
    """Blend `color` toward white. amount=0 returns it unchanged, 1.0 returns white."""
    amount = max(0.0, min(1.0, amount))
    return RGBColor(*(int(round(c + (0xFF - c) * amount)) for c in color))


def shade(color: RGBColor, amount: float) -> RGBColor:
    """Blend `color` toward black."""
    amount = max(0.0, min(1.0, amount))
    return RGBColor(*(int(round(c * (1.0 - amount))) for c in color))


# Derived surfaces - kept as expressions so the palette above stays the origin.
PANEL_BG = tint(GRAY_LIGHT, 0.45)  # considerations panel / side panels
ROW_TINT = tint(GRAY_LIGHT, 0.60)  # alternating table + gantt rows
SUBTITLE_GRAY = tint(GRAY_DARK, 0.45)
FOOTER_GRAY = tint(GRAY_DARK, 0.55)

RAG_COLORS = {
    "green": STATUS_GREEN,
    "amber": STATUS_AMBER,
    "red": STATUS_RED,
    "neutral": STATUS_NEUTRAL,
}

# Roadmap bars carry schedule state, not RAG. Keeping them in the primary hue
# family - with red reserved for genuine trouble - means a roadmap full of
# healthy bars never looks like a wall of traffic lights.
PHASE_COLORS = {
    "complete": tint(SECONDARY, 0.42),
    "in-progress": PRIMARY,
    "planned": tint(GRAY_DARK, 0.72),
    "at-risk": STATUS_RED,
}

PHASE_LABELS = {
    "complete": "Complete",
    "in-progress": "In progress",
    "planned": "Planned",
    "at-risk": "At risk",
}

SEVERITY_COLORS = {
    "H": STATUS_RED,
    "M": STATUS_AMBER,
    "L": STATUS_GREEN,
}

# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------

FONT = "Calibri"

FS_SECTION_NUMBER = 132  # oversized numeral on section dividers
FS_SECTION_TITLE = 30
FS_TITLE = 20  # bold action title
FS_SUBTITLE = 12  # one-line grey subtitle
FS_COLUMN_HEADER = 12
FS_BODY = 10
FS_DENSE = 9  # dense tables, charter bullets
FS_MICRO = 8  # footer, axis labels, badges

# Overflow search bounds, per text role.
FS_MIN_BODY = 7
FS_MIN_DENSE = 7
FS_MIN_TITLE = 14

LINE_SPACING = 0.92  # multiple; tightens dense bullet blocks
SPACE_AFTER_PT = 3.0  # between bullets

# --------------------------------------------------------------------------
# Slide grid
# --------------------------------------------------------------------------

SLIDE_W = 12192000  # 13.333"
SLIDE_H = 6858000  # 7.5"

MARGIN = inches(0.40)  # hard outer margin - nothing but full-bleed crosses it
GUTTER = inches(0.15)  # between columns

TITLE_H = inches(0.36)
TITLE_SUBTITLE_GAP = inches(0.04)
SUBTITLE_H = inches(0.24)
TITLE_BAND_H = TITLE_H + TITLE_SUBTITLE_GAP + SUBTITLE_H  # fixed for every layout
TITLE_CONTENT_GAP = inches(0.20)

FOOTER_H = inches(0.20)
FOOTER_CONTENT_GAP = inches(0.12)

# Considerations panel
PANEL_W_RATIO = 0.25
PANEL_PAD = inches(0.14)

# Shared shape metrics
CORNER_RADIUS_RATIO = 0.10  # for rounded rectangles, relative to short side
HAIRLINE_PT = 0.75
RULE_PT = 1.25
BADGE_D = inches(0.26)  # number badge diameter
CHIP_W = inches(0.42)
CHIP_H = inches(0.17)
TEXT_INSET = inches(0.07)  # internal padding inside text frames

MIN_SHAPE_GAP = inches(0.10)  # smallest visual gap the QA linter tolerates

# Roadmap metrics
GANTT_WP_COL_W = inches(1.12)
GANTT_SS_COL_W = inches(1.62)
GANTT_HEADER_H = inches(0.30)
GANTT_BAR_H_RATIO = 0.46  # of the row height, for a single-lane row
GANTT_MULTILANE_H_RATIO = 0.76  # rows that stack parallel phases need more of the row
GANTT_LANE_GAP = inches(0.022)
GANTT_BAR_MIN_W = inches(0.09)
GANTT_DIAMOND_D = inches(0.125)
GANTT_LEGEND_H = inches(0.24)
GANTT_LEGEND_GAP = inches(0.14)
GANTT_LEGEND_SWATCH_W = inches(0.20)
GANTT_LEGEND_ITEM_GAP = inches(0.26)
GANTT_LABEL_PAD = inches(0.06)
TODAY_LINE_PT = 1.5


# --------------------------------------------------------------------------
# Grid helpers
# --------------------------------------------------------------------------


def content_left() -> int:
    return MARGIN


def content_width() -> int:
    return SLIDE_W - 2 * MARGIN


def content_top() -> int:
    """Top of the body area, below the title band."""
    return MARGIN + TITLE_BAND_H + TITLE_CONTENT_GAP


def content_bottom() -> int:
    """Bottom of the body area, above the footer."""
    return SLIDE_H - MARGIN - FOOTER_H - FOOTER_CONTENT_GAP


def content_height() -> int:
    return content_bottom() - content_top()


def footer_top() -> int:
    return SLIDE_H - MARGIN - FOOTER_H


def panel_width(total: int | None = None) -> int:
    """Width of the right-hand considerations panel."""
    return int(round((content_width() if total is None else total) * PANEL_W_RATIO))


def panel_left(total: int | None = None) -> int:
    total = content_width() if total is None else total
    return content_left() + total - panel_width(total)


def body_width_with_panel(total: int | None = None) -> int:
    """Usable body width once a considerations panel takes the right-hand quarter."""
    total = content_width() if total is None else total
    return total - panel_width(total) - GUTTER


def col_w(n: int, total: int | None = None, gutter: int | None = None) -> int:
    """Width of one of `n` equal columns spanning `total` (default: full content width)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    total = content_width() if total is None else total
    gutter = GUTTER if gutter is None else gutter
    return int((total - (n - 1) * gutter) // n)


def col_x(i: int, n: int, total: int | None = None, x0: int | None = None,
          gutter: int | None = None) -> int:
    """Left edge of column `i` (0-based) in an `n`-column grid."""
    if not 0 <= i < n:
        raise IndexError(f"column {i} out of range for {n} columns")
    x0 = content_left() if x0 is None else x0
    gutter = GUTTER if gutter is None else gutter
    return x0 + i * (col_w(n, total, gutter) + gutter)


def row_h(n: int, total: int | None = None, gutter: int | None = None) -> int:
    """Height of one of `n` equal rows spanning `total` (default: full content height)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    total = content_height() if total is None else total
    gutter = GUTTER if gutter is None else gutter
    return int((total - (n - 1) * gutter) // n)


def row_y(i: int, n: int, total: int | None = None, y0: int | None = None,
         gutter: int | None = None) -> int:
    """Top edge of row `i` (0-based) in an `n`-row grid."""
    if not 0 <= i < n:
        raise IndexError(f"row {i} out of range for {n} rows")
    y0 = content_top() if y0 is None else y0
    gutter = GUTTER if gutter is None else gutter
    return y0 + i * (row_h(n, total, gutter) + gutter)


FOOTER_NOTE = "Northwind GBS - Project Meridian | Internal draft, not for distribution"
