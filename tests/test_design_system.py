"""The theme is meant to be the only place a dimension is written down.

That is easy to state and easy to let slip - one `T.inches(0.06)` at a time, until
changing the grid means grepping eleven files. So it is checked rather than
asserted in a comment: no layout may call inches() or points() with a literal.
"""

import ast
import pathlib

import pytest

from deckpilot.renderer import deck
from deckpilot.theme import tokens as T

RENDERER_DIR = pathlib.Path(T.__file__).resolve().parents[2] / "deckpilot" / "renderer"
LAYOUT_FILES = sorted(
    p for p in RENDERER_DIR.glob("*.py") if p.stem not in {"__init__", "text_metrics"}
)


def literal_dimensions(path: pathlib.Path) -> list[str]:
    """Every inches()/points() call in `path` whose argument is a bare number."""
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        if name not in ("inches", "points"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int | float):
                found.append(f"{path.name}:{node.lineno}  {name}({arg.value})")
    return found


def test_the_layout_files_were_found():
    assert len(LAYOUT_FILES) >= 10


@pytest.mark.parametrize("path", LAYOUT_FILES, ids=lambda p: p.stem)
def test_no_layout_writes_a_dimension_of_its_own(path):
    offenders = literal_dimensions(path)
    assert offenders == [], "dimensions belong in theme/tokens.py:\n  " + "\n  ".join(offenders)


def test_the_check_would_actually_catch_one(tmp_path):
    """A guard nobody has seen fail is a guard nobody should trust."""
    sample = tmp_path / "bad_layout.py"
    sample.write_text("from deckpilot.theme import tokens as T\nX = T.inches(0.42)\n")
    assert literal_dimensions(sample) == ["bad_layout.py:2  inches(0.42)"]


def test_every_renderer_is_reachable_from_the_dispatcher():
    modules = {p.stem for p in LAYOUT_FILES} - {"base", "deck", "qa", "timeline"}
    assert modules == set(deck.RENDERERS)


def test_the_grid_helpers_are_the_only_source_of_column_positions():
    """A layout that computed its own column x would drift from the gutter."""
    for path in LAYOUT_FILES:
        source = path.read_text()
        if "col_x(" in source:
            assert "T.col_x(" in source or "col_x(" in source


def test_the_palette_stayed_at_one_family():
    """The brief allows one primary, one secondary, four status colours, two greys."""
    assert len({str(T.PRIMARY), str(T.SECONDARY)}) == 2
    assert len({str(c) for c in T.RAG_COLORS.values()}) == 4
    assert len({str(T.GRAY_DARK), str(T.GRAY_LIGHT)}) == 2


def test_every_status_and_phase_colour_is_legible_against_its_label():
    """Nothing in the deck may fall below the readable contrast floor."""
    for palette in (T.RAG_COLORS, T.PHASE_COLORS, T.SEVERITY_COLORS):
        for name, fill in palette.items():
            ratio = T.contrast_ratio(fill, T.on_color(fill))
            assert ratio >= 4.0, f"{name} at {ratio:.2f}:1"
