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
    # Speaker notes travel with the slide because they are content, not layout.
    notes: str = Field(default="", max_length=1600)


# --------------------------------------------------------------------------
# 1. Section divider
# --------------------------------------------------------------------------


class SectionDividerSpec(Spec):
    layout: Literal["section_divider"] = "section_divider"
    number: str = Field(min_length=1, max_length=2)
    title: str = Field(min_length=1, max_length=60)
    kicker: str | None = Field(default=None, max_length=120)
    notes: str = Field(default="", max_length=1600)


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
# 5. RAID table
# --------------------------------------------------------------------------

Severity = Literal["H", "M", "L"]
RaidKind = Literal["risk", "assumption", "issue", "dependency"]


class RaidRow(Spec):
    id: str = Field(min_length=1, max_length=8)
    kind: RaidKind
    severity: Severity
    title: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=40)
    due: str = Field(min_length=1, max_length=16)
    mitigation: str = Field(min_length=1, max_length=200)


class RaidTableSpec(SlideBase):
    layout: Literal["raid_table"] = "raid_table"
    rows: list[RaidRow] = Field(min_length=1, max_length=20)
    # Set when a log is long enough to need more than one slide.
    continued_groups: list[RaidKind] = Field(default_factory=list)
    group_labels: dict[str, str] = Field(
        default_factory=lambda: {
            "risk": "Risks",
            "issue": "Issues",
            "dependency": "Dependencies",
            "assumption": "Assumptions",
        }
    )


# --------------------------------------------------------------------------
# 6. Status overview
# --------------------------------------------------------------------------

RagValue = Literal["green", "amber", "red"]


class StatusCard(Spec):
    number: str = Field(min_length=1, max_length=3)
    name: str = Field(min_length=1, max_length=60)
    rag: RagValue
    progress_pct: int = Field(ge=0, le=100)
    activities: list[str] = Field(min_length=1, max_length=3)
    next_milestone: str = Field(default="", max_length=90)


class StatusOverviewSpec(SlideBase):
    layout: Literal["status_overview"] = "status_overview"
    cards: list[StatusCard] = Field(min_length=2, max_length=6)


# --------------------------------------------------------------------------
# 7. Criteria columns
# --------------------------------------------------------------------------


class CriteriaColumn(Spec):
    question: str = Field(min_length=1, max_length=80)
    caption: str | None = Field(default=None, max_length=60)
    characteristics: list[str] = Field(min_length=1, max_length=6)
    state: Literal["passed", "upcoming", "at-risk", "neutral"] = "neutral"


class CriteriaColumnsSpec(SlideBase):
    layout: Literal["criteria_columns"] = "criteria_columns"
    columns: list[CriteriaColumn] = Field(min_length=2, max_length=5)
    characteristics_label: str = "Characteristics"


# --------------------------------------------------------------------------
# 8. Executive summary
# --------------------------------------------------------------------------


class KeyMessage(Spec):
    heading: str = Field(min_length=1, max_length=70)
    detail: str = Field(min_length=1, max_length=260)
    rag: RagValue = "green"


class ExecSummarySpec(SlideBase):
    layout: Literal["exec_summary"] = "exec_summary"
    overall_rag: RagValue
    verdict: str = Field(min_length=1, max_length=180)
    messages: list[KeyMessage] = Field(min_length=2, max_length=4)
    decisions: list[str] = Field(default_factory=list, max_length=4)
    decisions_label: str = "Decisions needed"


# --------------------------------------------------------------------------
# 9. KPI scorecard
# --------------------------------------------------------------------------


class BenefitRow(Spec):
    name: str = Field(min_length=1, max_length=60)
    owner: str = Field(min_length=1, max_length=40)
    baseline: str = Field(min_length=1, max_length=16)
    current: str = Field(min_length=1, max_length=16)
    target: str = Field(min_length=1, max_length=16)
    attainment: float = Field(ge=0.0, le=1.0)
    expected: float = Field(ge=0.0, le=1.0)


class KpiScorecardSpec(SlideBase):
    layout: Literal["kpi_scorecard"] = "kpi_scorecard"
    rows: list[BenefitRow] = Field(min_length=1, max_length=10)
    expected_label: str = "Delivery progress of the producing stream"


# --------------------------------------------------------------------------
# 10. Agenda
# --------------------------------------------------------------------------


class AgendaEntry(Spec):
    number: str = Field(min_length=1, max_length=2)
    title: str = Field(min_length=1, max_length=60)
    caption: str | None = Field(default=None, max_length=120)
    page: int = Field(ge=1)


class AgendaSpec(SlideBase):
    layout: Literal["agenda"] = "agenda"
    entries: list[AgendaEntry] = Field(min_length=2, max_length=8)


# --------------------------------------------------------------------------
# 11. Benefits bridge
# --------------------------------------------------------------------------


class BridgeStep(Spec):
    """One column of a waterfall.

    `from_value` and `to_value` are the levels either side of the step, so the
    layout never has to work out a running total - it only has to map values to
    pixels. An anchor has the two equal and is drawn from the axis floor.
    """

    label: str = Field(min_length=1, max_length=60)
    caption: str | None = Field(default=None, max_length=40)
    kind: Literal["anchor", "increase", "decrease"]
    from_value: float
    to_value: float
    value: str = Field(min_length=1, max_length=16)


class BenefitsBridgeSpec(SlideBase):
    layout: Literal["benefits_bridge"] = "benefits_bridge"
    unit: str = Field(min_length=1, max_length=12)
    steps: list[BridgeStep] = Field(min_length=3, max_length=10)


# --------------------------------------------------------------------------
# Deck
# --------------------------------------------------------------------------

AnySlideSpec = Annotated[
    SectionDividerSpec
    | WorkstreamCharterSpec
    | RoadmapGanttSpec
    | GovernanceChartSpec
    | RaidTableSpec
    | StatusOverviewSpec
    | CriteriaColumnsSpec
    | ExecSummarySpec
    | KpiScorecardSpec
    | AgendaSpec
    | BenefitsBridgeSpec,
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
