"""Slide specifications: what goes on a slide, never where it goes.

A spec is the contract between content selection (deterministic builder or LLM)
and layout. Content decisions - which RAID items make the cut, how the action
title is phrased - live here. Position, size and colour do not: those are the
renderer's, derived from the theme. That split is what keeps an LLM from being
able to break the layout.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SlideBase(Spec):
    title: str = Field(min_length=1, max_length=160)
    subtitle: str | None = Field(default=None, max_length=200)
    considerations: list[str] = Field(default_factory=list, max_length=6)


# --------------------------------------------------------------------------
# 1. Section divider
# --------------------------------------------------------------------------


class SectionDividerSpec(Spec):
    layout: Literal["section_divider"] = "section_divider"
    number: str = Field(min_length=1, max_length=2)
    title: str = Field(min_length=1, max_length=60)
    kicker: str | None = Field(default=None, max_length=120)


# --------------------------------------------------------------------------
# 2. Workstream charter
# --------------------------------------------------------------------------


class CharterColumn(Spec):
    number: str = Field(min_length=1, max_length=3)
    name: str = Field(min_length=1, max_length=60)
    activities: list[str] = Field(min_length=1, max_length=6)
    outcomes: list[str] = Field(min_length=1, max_length=5)


class WorkstreamCharterSpec(SlideBase):
    layout: Literal["workstream_charter"] = "workstream_charter"
    columns: list[CharterColumn] = Field(min_length=3, max_length=5)
    activities_label: str = "Key activities"
    outcomes_label: str = "Outcomes"


# --------------------------------------------------------------------------
# 3. Roadmap gantt
# --------------------------------------------------------------------------

PhaseState = Literal["complete", "in-progress", "planned", "at-risk"]


class GanttBar(Spec):
    label: str = Field(default="", max_length=48)
    start: date
    end: date
    status: PhaseState = "planned"


class GanttMilestone(Spec):
    name: str = Field(min_length=1, max_length=80)
    date: date
    major: bool = False


class GanttRow(Spec):
    work_package: str = Field(min_length=1, max_length=48)
    sub_stream: str = Field(min_length=1, max_length=48)
    bars: list[GanttBar] = Field(default_factory=list, max_length=8)
    milestones: list[GanttMilestone] = Field(default_factory=list, max_length=8)


class RoadmapGanttSpec(SlideBase):
    layout: Literal["roadmap_gantt"] = "roadmap_gantt"
    window_start: date
    window_end: date
    today: date | None = None
    rows: list[GanttRow] = Field(min_length=2, max_length=16)


# --------------------------------------------------------------------------
# 4. Governance chart
# --------------------------------------------------------------------------


class GovernanceBox(Spec):
    title: str = Field(min_length=1, max_length=48)
    caption: str | None = Field(default=None, max_length=48)
    members: list[str] = Field(min_length=1, max_length=8)


class GovernanceUnit(Spec):
    number: str = Field(min_length=1, max_length=3)
    name: str = Field(min_length=1, max_length=48)
    core_team: list[str] = Field(min_length=1, max_length=5)
    contributing_teams: list[str] = Field(min_length=1, max_length=6)


class GovernanceChartSpec(SlideBase):
    layout: Literal["governance_chart"] = "governance_chart"
    steering: GovernanceBox
    programme_management: GovernanceBox
    units: list[GovernanceUnit] = Field(min_length=2, max_length=5)
    core_label: str = "Core team"
    contributing_label: str = "Contributing teams"


# --------------------------------------------------------------------------
# Deck
# --------------------------------------------------------------------------

AnySlideSpec = Annotated[
    SectionDividerSpec | WorkstreamCharterSpec | RoadmapGanttSpec | GovernanceChartSpec,
    Field(discriminator="layout"),
]


class DeckSpec(Spec):
    title: str
    subtitle: str
    week: str
    slides: list[AnySlideSpec] = Field(min_length=1)

    @classmethod
    def load(cls, path: str | Path) -> DeckSpec:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(self.model_dump_json(exclude_none=True))
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
