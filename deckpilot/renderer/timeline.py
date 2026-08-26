"""Date-to-position maths for the roadmap grid.

Kept separate from the drawing code because this is where a roadmap actually
goes wrong: a bar that starts before the window, a bar that ends after it, a
milestone on the last day of the last month, a one-day task that rounds away to
nothing. Those are arithmetic problems, and they are much easier to test as
arithmetic than by looking at a slide.

Months are drawn at equal width rather than in proportion to their length. A
grid whose February column is shorter than its March column looks like a
rendering fault, and no reader is measuring a roadmap to the day.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

MONTH_INITIALS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def months_between(start: date, end: date) -> list[tuple[int, int]]:
    """Every (year, month) touched by the window, inclusive at both ends."""
    if end < start:
        raise ValueError(f"window ends ({end}) before it starts ({start})")
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


@dataclass(frozen=True)
class MonthGrid:
    """Maps dates onto a horizontal band of `width` EMU starting at `x`."""

    start: date
    end: date
    x: int
    width: int

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("grid width must be positive")
        object.__setattr__(self, "_months", tuple(months_between(self.start, self.end)))

    @property
    def months(self) -> tuple[tuple[int, int], ...]:
        return self._months  # type: ignore[attr-defined]

    @property
    def month_count(self) -> int:
        return len(self.months)

    @property
    def month_width(self) -> float:
        return self.width / self.month_count

    @property
    def right(self) -> int:
        return self.x + self.width

    def month_x(self, index: int) -> float:
        """Left edge of the month at `index`."""
        return self.x + index * self.month_width

    def position(self, day: date) -> float:
        """Unclamped x for `day`. May fall outside the grid; that is the caller's problem."""
        first_year, first_month = self.months[0]
        index = (day.year - first_year) * 12 + (day.month - first_month)
        days_in_month = monthrange(day.year, day.month)[1]
        return self.x + (index + (day.day - 1) / days_in_month) * self.month_width

    def clamped(self, day: date) -> float:
        return min(max(self.position(day), float(self.x)), float(self.right))

    def is_visible(self, day: date) -> bool:
        return self.start <= day <= self.end

    def bar(self, start: date, end: date, min_width: int = 0) -> tuple[int, int] | None:
        """Pixel extent of a bar running `start`..`end` inclusive, clipped to the grid.

        Returns None when the bar lies entirely outside the window. A bar that
        straddles an edge is cut at the edge rather than drawn overhanging it.
        """
        if end < start:
            raise ValueError(f"bar ends ({end}) before it starts ({start})")
        if end < self.start or start > self.end:
            return None

        left = self.position(start)
        # `end` is inclusive, so the bar covers that whole day.
        days_in_month = monthrange(end.year, end.month)[1]
        right = self.position(end) + self.month_width / days_in_month

        left = max(left, float(self.x))
        right = min(right, float(self.right))
        if right <= left:
            return None

        x = int(round(left))
        width = int(round(right - left))
        if width < min_width:
            width = min_width
            # Widening must not push the bar past the grid's right edge.
            if x + width > self.right:
                x = self.right - width
            x = max(x, self.x)
        return x, width

    def labels(self, abbreviated: bool = True) -> list[str]:
        """Month captions. January carries its year so the reader can see the roll-over."""
        out = []
        for i, (year, month) in enumerate(self.months):
            name = (MONTH_ABBR if abbreviated else MONTH_INITIALS)[month - 1]
            out.append(f"{name} {str(year)[2:]}" if month == 1 or i == 0 else name)
        return out


def assign_lanes(spans: list[tuple[date, date]]) -> tuple[list[int], int]:
    """Pack time spans into as few non-overlapping lanes as possible.

    A sub-stream whose phases genuinely run in parallel - two migration waves
    that overlap by seven weeks - must show them stacked. Drawing them on one
    line would hide exactly the fact the roadmap exists to show.

    Returns the lane index for each span, in the input order, and the lane count.
    """
    lanes_end: list[date] = []
    lane_of = [0] * len(spans)
    for i in sorted(range(len(spans)), key=lambda k: (spans[k][0], spans[k][1])):
        start, end = spans[i]
        for lane, last_end in enumerate(lanes_end):
            if start > last_end:
                lanes_end[lane] = end
                lane_of[i] = lane
                break
        else:
            lanes_end.append(end)
            lane_of[i] = len(lanes_end) - 1
    return lane_of, max(1, len(lanes_end))
