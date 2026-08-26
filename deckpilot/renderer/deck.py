"""Turn a deck specification into a presentation.

The only thing this module decides is which layout function handles which spec
and what page number it gets. Everything else was settled upstream: content by
the spec builder, position by the layout.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pptx.presentation import Presentation as PresentationType

from deckpilot.renderer import (
    criteria_columns,
    exec_summary,
    governance_chart,
    kpi_scorecard,
    raid_table,
    roadmap_gantt,
    section_divider,
    status_overview,
    workstream_charter,
)
from deckpilot.renderer.base import new_deck
from deckpilot.specgen.schema import DeckSpec

log = logging.getLogger("deckpilot.renderer")

# A section divider takes no page number - it carries no footer - but it still
# occupies a page, so the count runs through it.
RENDERERS = {
    "section_divider": lambda prs, spec, page: section_divider.render(prs, spec),
    "workstream_charter": workstream_charter.render,
    "roadmap_gantt": roadmap_gantt.render,
    "governance_chart": governance_chart.render,
    "raid_table": raid_table.render,
    "status_overview": status_overview.render,
    "criteria_columns": criteria_columns.render,
    "exec_summary": exec_summary.render,
    "kpi_scorecard": kpi_scorecard.render,
}


def build(spec: DeckSpec) -> PresentationType:
    prs = new_deck()
    for page, slide_spec in enumerate(spec.slides, start=1):
        render = RENDERERS.get(slide_spec.layout)
        if render is None:  # pragma: no cover - the schema forbids it
            raise KeyError(f"no renderer for layout {slide_spec.layout!r}")
        render(prs, slide_spec, page)
    return prs


def build_to(spec: DeckSpec, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    build(spec).save(str(path))
    log.info("wrote %s (%d slides)", path, len(spec.slides))
    return path
