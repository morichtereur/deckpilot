"""Text measurement for Calibri.

python-pptx writes XML; it does not render, so it cannot tell us whether a string
fits its box. PowerPoint's own autofit is not an option either: it is applied at
open time by the client, so a deck built here would look different depending on
who opened it, and the `.pptx` on disk would contain sizes we never chose.

So we measure ourselves. The table below holds Calibri advance widths in units
per 1000 em, which is enough to wrap a paragraph and count lines to within a
character or two. Every fitting decision is then made at build time and written
into the file as an explicit font size.
"""

from __future__ import annotations

# Calibri advance widths, units per 1000 em.
_W: dict[str, int] = {
    " ": 226, "!": 234, '"': 348, "#": 498, "$": 498, "%": 834, "&": 622, "'": 169,
    "(": 303, ")": 303, "*": 397, "+": 498, ",": 246, "-": 306, ".": 246, "/": 361,
    "0": 507, "1": 507, "2": 507, "3": 507, "4": 507, "5": 507, "6": 507, "7": 507,
    "8": 507, "9": 507, ":": 267, ";": 267, "<": 498, "=": 498, ">": 498, "?": 415,
    "@": 850, "[": 303, "\\": 361, "]": 303, "^": 498, "_": 498, "`": 300, "{": 303,
    "|": 236, "}": 303, "~": 498,
    "A": 579, "B": 544, "C": 533, "D": 615, "E": 488, "F": 459, "G": 631, "H": 623,
    "I": 252, "J": 319, "K": 520, "L": 420, "M": 855, "N": 646, "O": 662, "P": 517,
    "Q": 673, "R": 543, "S": 459, "T": 487, "U": 642, "V": 567, "W": 890, "X": 519,
    "Y": 487, "Z": 468,
    "a": 479, "b": 525, "c": 423, "d": 525, "e": 498, "f": 305, "g": 471, "h": 525,
    "i": 229, "j": 239, "k": 455, "l": 229, "m": 799, "n": 525, "o": 527, "p": 525,
    "q": 525, "r": 349, "s": 391, "t": 335, "u": 525, "v": 452, "w": 715, "x": 433,
    "y": 453, "z": 395,
    "–": 500, "—": 1000, "‘": 169, "’": 169, "“": 348,
    "”": 348, "•": 350, "…": 738, " ": 226,
}

_DEFAULT_W = 500
BOLD_FACTOR = 1.045  # Calibri Bold runs a little wider than regular
LINE_HEIGHT_FACTOR = 1.22  # Calibri's default line box, as a multiple of font size
ELLIPSIS = "…"


def char_width(ch: str, size_pt: float, bold: bool = False) -> float:
    w = _W.get(ch, _DEFAULT_W) / 1000.0 * size_pt
    return w * BOLD_FACTOR if bold else w


def text_width(text: str, size_pt: float, bold: bool = False) -> float:
    """Rendered width of `text` in points, unwrapped."""
    total = sum(_W.get(ch, _DEFAULT_W) for ch in text) / 1000.0 * size_pt
    return total * BOLD_FACTOR if bold else total


def wrap(text: str, width_pt: float, size_pt: float, bold: bool = False) -> list[str]:
    """Greedy word wrap, matching how PowerPoint breaks a paragraph.

    A word longer than the line is broken mid-word rather than allowed to
    overhang, which is also what PowerPoint does.
    """
    if width_pt <= 0:
        return [text]
    lines: list[str] = []
    for hard_line in text.split("\n"):
        words = hard_line.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_width(candidate, size_pt, bold) <= width_pt:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # The word alone may still be too wide for the line.
            while text_width(word, size_pt, bold) > width_pt:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], size_pt, bold) > width_pt:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


def line_count(text: str, width_pt: float, size_pt: float, bold: bool = False) -> int:
    return len(wrap(text, width_pt, size_pt, bold))


def block_height(
    paragraphs: list[str],
    width_pt: float,
    size_pt: float,
    bold: bool = False,
    line_spacing: float = 1.0,
    space_after_pt: float = 0.0,
) -> float:
    """Height in points of a run of paragraphs laid out at `size_pt`."""
    if not paragraphs:
        return 0.0
    line_h = size_pt * LINE_HEIGHT_FACTOR * line_spacing
    lines = sum(line_count(p, width_pt, size_pt, bold) for p in paragraphs)
    return lines * line_h + space_after_pt * (len(paragraphs) - 1)


def truncate(text: str, width_pt: float, size_pt: float, max_lines: int, bold: bool = False) -> str:
    """Shorten `text` so it occupies at most `max_lines`, ending in an ellipsis."""
    if max_lines < 1:
        return ELLIPSIS
    if line_count(text, width_pt, size_pt, bold) <= max_lines:
        return text
    lo, hi = 0, len(text)
    best = ""
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid].rstrip() + ELLIPSIS
        if line_count(candidate, width_pt, size_pt, bold) <= max_lines:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best or ELLIPSIS
