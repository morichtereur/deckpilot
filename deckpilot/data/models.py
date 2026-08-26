"""Programme data model.

This is the input contract for the whole pipeline: a transformation programme
described richly enough that slides can be derived from it without any layout
code inventing content. Cross-references (a RAID item pointing at a sub-stream,
a milestone pointing at a work package) are validated at load time, so a deck
build fails on inconsistent data rather than rendering a dangling reference.
"""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class RAG(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Severity(StrEnum):
    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


class GateStatus(StrEnum):
    PASSED = "passed"
    UPCOMING = "upcoming"
    AT_RISK = "at-risk"


class RaidType(StrEnum):
    RISK = "risk"
    ASSUMPTION = "assumption"
    ISSUE = "issue"
    DEPENDENCY = "dependency"


class PhaseStatus(StrEnum):
    COMPLETE = "complete"
    IN_PROGRESS = "in-progress"
    PLANNED = "planned"
    AT_RISK = "at-risk"


class BenefitDirection(StrEnum):
    """Whether a measure improves by going up or by going down."""

    UP = "up"
    DOWN = "down"


class MilestoneStatus(StrEnum):
    ACHIEVED = "achieved"
    ON_TRACK = "on-track"
    AT_RISK = "at-risk"
    MISSED = "missed"


Pct = Annotated[int, Field(ge=0, le=100)]


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------
# People and teams
# --------------------------------------------------------------------------


class Person(Base):
    name: str
    role: str
    org: str | None = None


class Team(Base):
    name: str
    note: str | None = None


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------


class Phase(Base):
    """One bar on the roadmap. A sub-stream is delivered as a sequence of these."""

    name: str
    start: date
    end: date
    status: PhaseStatus

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError(
                f"phase '{self.name}' ends ({self.end}) before it starts ({self.start})"
            )
        return self


class SubStream(Base):
    id: str
    name: str
    lead: str
    objective: str
    phases: list[Phase] = Field(min_length=1)

    @property
    def start(self) -> date:
        return min(p.start for p in self.phases)

    @property
    def end(self) -> date:
        return max(p.end for p in self.phases)


class WorkPackage(Base):
    id: str
    number: int
    name: str
    objective: str
    lead: str
    sub_streams: list[SubStream] = Field(min_length=2, max_length=4)
    core_team: list[Team] = Field(min_length=1)
    contributing_teams: list[Team] = Field(min_length=1)


class StageGate(Base):
    id: str
    number: int
    name: str
    date: date
    status: GateStatus
    criteria: list[str] = Field(min_length=1)


class RaidItem(Base):
    id: str
    type: RaidType
    title: str
    description: str
    severity: Severity
    owner: str
    raised: date
    due: date
    mitigation: str
    sub_stream_id: str

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.due < self.raised:
            raise ValueError(
                f"RAID {self.id} is due ({self.due}) before it was raised ({self.raised})"
            )
        return self


class Milestone(Base):
    id: str
    name: str
    date: date
    sub_stream_id: str
    status: MilestoneStatus
    major: bool = False


class BenefitMeasure(Base):
    """One tracked measure, from where it started to where it has to get to."""

    id: str
    name: str
    unit: str
    baseline: float
    current: float
    target: float
    owner: str
    sub_stream_id: str
    direction: BenefitDirection
    as_of: date

    @model_validator(mode="after")
    def _target_moves(self) -> Self:
        if self.target == self.baseline:
            raise ValueError(f"benefit {self.id} has a target equal to its baseline")
        improving_up = self.direction is BenefitDirection.UP
        if improving_up != (self.target > self.baseline):
            raise ValueError(
                f"benefit {self.id} is declared {self.direction.value} but its target "
                f"({self.target}) moves the other way from its baseline ({self.baseline})"
            )
        return self

    @property
    def attainment(self) -> float:
        """How far the measure has travelled from baseline to target, 0.0 to 1.0.

        Clamped: a measure that has overshot its target is at 1.0, and one that
        has moved backwards is at 0.0. Both are reported honestly elsewhere - the
        clamp only keeps a progress bar inside its track.
        """
        span = self.target - self.baseline
        moved = self.current - self.baseline
        return max(0.0, min(1.0, moved / span))

    @property
    def moved_backwards(self) -> bool:
        span = self.target - self.baseline
        return (self.current - self.baseline) / span < 0

    def plain(self, value: float) -> str:
        """The bare number, with no unit and no trailing zero."""
        return f"{int(value)}" if value == int(value) else f"{value:.1f}"

    def format(self, value: float) -> str:
        """A measure's value carrying its unit, for prose."""
        if self.unit == "%":
            return f"{self.plain(value)}%"
        return f"{self.plain(value)} {self.unit}".strip()

    @property
    def display_name(self) -> str:
        """The measure's name carrying its unit, so the figures can go bare.

        A scorecard column repeating "EUR m" on every row wraps the number onto a
        second line and tells the reader nothing they did not already know. A unit
        the name already carries - "Change readiness index (index)" - is dropped.
        """
        if self.unit == "%" or self.unit.lower() in self.name.lower():
            return self.name
        return f"{self.name} ({self.unit})"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BenefitLever(Base):
    """One step of the cost bridge.

    `value` is signed and expressed in the case's unit: negative takes cost out,
    positive puts it back. A bridge with no positive step is usually a bridge
    that has forgotten what the new operating model costs to run.
    """

    id: str
    name: str
    value: float
    confidence: Confidence
    owner: str
    sub_stream_id: str | None = None

    @property
    def is_saving(self) -> bool:
        return self.value < 0

    @property
    def short_name(self) -> str:
        """The lever's name trimmed to its first idea, for use inside a sentence.

        "Process standardisation and automation" is the right label under a
        column and too long inside an action title.
        """
        for joiner in (" and ", " & "):
            if joiner in self.name:
                return self.name.split(joiner)[0]
        return self.name


class BenefitCase(Base):
    """Baseline cost, the levers that move it, and where it lands."""

    unit: str
    baseline_label: str
    baseline: float
    target_label: str
    target: float
    levers: list[BenefitLever] = Field(min_length=1)

    @model_validator(mode="after")
    def _bridge_reconciles(self) -> Self:
        computed = self.baseline + sum(lever.value for lever in self.levers)
        if abs(computed - self.target) > 0.05:
            raise ValueError(
                f"the benefit case does not bridge: {self.baseline} plus the levers "
                f"gives {computed:.2f}, but the target is {self.target}"
            )
        return self

    @property
    def running_totals(self) -> list[float]:
        """The value at the top of each step, baseline first, target last."""
        totals, running = [self.baseline], self.baseline
        for lever in self.levers:
            running += lever.value
            totals.append(running)
        return totals

    @property
    def total_saving(self) -> float:
        return self.baseline - self.target


class WeeklyStatus(Base):
    """One sub-stream's report for one ISO week."""

    week: str = Field(pattern=r"^\d{4}-W\d{2}$")
    sub_stream_id: str
    rag: RAG
    progress_pct: Pct
    headline: str
    activities: list[str] = Field(min_length=3, max_length=5)
    decisions_needed: list[str] = Field(default_factory=list)
    next_milestone_id: str | None = None


class Governance(Base):
    steering_committee: list[Person] = Field(min_length=3)
    steering_cadence: str
    programme_management: list[Person] = Field(min_length=2)
    pmo_cadence: str
    comments: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Root
# --------------------------------------------------------------------------


class Programme(Base):
    name: str
    client: str
    subtitle: str
    start: date
    end: date
    work_packages: list[WorkPackage] = Field(min_length=1)
    stage_gates: list[StageGate] = Field(min_length=1)
    raid: list[RaidItem] = Field(min_length=1)
    milestones: list[Milestone] = Field(min_length=1)
    weekly_status: list[WeeklyStatus] = Field(min_length=1)
    benefits: list[BenefitMeasure] = Field(default_factory=list)
    benefit_case: BenefitCase | None = None
    governance: Governance

    # -- lookups ----------------------------------------------------------

    @property
    def sub_streams(self) -> list[SubStream]:
        return [ss for wp in self.work_packages for ss in wp.sub_streams]

    def sub_stream(self, sub_stream_id: str) -> SubStream:
        for ss in self.sub_streams:
            if ss.id == sub_stream_id:
                return ss
        raise KeyError(sub_stream_id)

    def work_package(self, work_package_id: str) -> WorkPackage:
        for wp in self.work_packages:
            if wp.id == work_package_id:
                return wp
        raise KeyError(work_package_id)

    def work_package_of(self, sub_stream_id: str) -> WorkPackage:
        for wp in self.work_packages:
            if any(ss.id == sub_stream_id for ss in wp.sub_streams):
                return wp
        raise KeyError(sub_stream_id)

    def benefit(self, benefit_id: str) -> BenefitMeasure:
        for b in self.benefits:
            if b.id == benefit_id:
                return b
        raise KeyError(benefit_id)

    def elapsed_fraction(self, as_of: date) -> float:
        """How far through the programme window `as_of` sits, 0.0 to 1.0."""
        total = (self.end - self.start).days
        return max(0.0, min(1.0, (as_of - self.start).days / total)) if total else 0.0

    def milestone(self, milestone_id: str) -> Milestone:
        for m in self.milestones:
            if m.id == milestone_id:
                return m
        raise KeyError(milestone_id)

    def weeks(self) -> list[str]:
        return sorted({ws.week for ws in self.weekly_status})

    def status_for_week(self, week: str) -> list[WeeklyStatus]:
        """Weekly reports for `week`, ordered to match work package / sub-stream order."""
        by_id = {ws.sub_stream_id: ws for ws in self.weekly_status if ws.week == week}
        return [by_id[ss.id] for ss in self.sub_streams if ss.id in by_id]

    # -- consistency ------------------------------------------------------

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.end <= self.start:
            raise ValueError("programme ends before it starts")

        ss_ids = [ss.id for wp in self.work_packages for ss in wp.sub_streams]
        dupes = {i for i in ss_ids if ss_ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate sub-stream ids: {sorted(dupes)}")
        known_ss = set(ss_ids)

        ms_ids = [m.id for m in self.milestones]
        if len(set(ms_ids)) != len(ms_ids):
            raise ValueError("duplicate milestone ids")

        window = (self.start, self.end)
        for wp in self.work_packages:
            for ss in wp.sub_streams:
                for ph in ss.phases:
                    if not (window[0] <= ph.start and ph.end <= window[1]):
                        raise ValueError(
                            f"phase '{ss.id}/{ph.name}' ({ph.start}..{ph.end}) "
                            f"falls outside the programme window {window[0]}..{window[1]}"
                        )

        for g in self.stage_gates:
            if not window[0] <= g.date <= window[1]:
                raise ValueError(f"stage gate {g.id} on {g.date} is outside the programme window")

        for item in self.raid:
            if item.sub_stream_id not in known_ss:
                raise ValueError(
                    f"RAID {item.id} references unknown sub-stream {item.sub_stream_id!r}"
                )

        for m in self.milestones:
            if m.sub_stream_id not in known_ss:
                raise ValueError(
                    f"milestone {m.id} references unknown sub-stream {m.sub_stream_id!r}"
                )
            if not window[0] <= m.date <= window[1]:
                raise ValueError(f"milestone {m.id} on {m.date} is outside the programme window")

        known_ms = set(ms_ids)
        for ws in self.weekly_status:
            if ws.sub_stream_id not in known_ss:
                raise ValueError(
                    f"weekly status {ws.week}/{ws.sub_stream_id} references an unknown sub-stream"
                )
            if ws.next_milestone_id is not None and ws.next_milestone_id not in known_ms:
                raise ValueError(
                    f"weekly status {ws.week}/{ws.sub_stream_id} references "
                    f"unknown milestone {ws.next_milestone_id!r}"
                )

        for benefit in self.benefits:
            if benefit.sub_stream_id not in known_ss:
                raise ValueError(
                    f"benefit {benefit.id} references unknown sub-stream "
                    f"{benefit.sub_stream_id!r}"
                )
            if not window[0] <= benefit.as_of <= window[1]:
                raise ValueError(
                    f"benefit {benefit.id} is measured on {benefit.as_of}, "
                    f"outside the programme window"
                )

        if self.benefit_case is not None:
            for lever in self.benefit_case.levers:
                if lever.sub_stream_id is not None and lever.sub_stream_id not in known_ss:
                    raise ValueError(
                        f"benefit lever {lever.id} references unknown sub-stream "
                        f"{lever.sub_stream_id!r}"
                    )

        benefit_ids = [b.id for b in self.benefits]
        if len(set(benefit_ids)) != len(benefit_ids):
            raise ValueError("duplicate benefit ids")

        seen: set[tuple[str, str]] = set()
        for ws in self.weekly_status:
            key = (ws.week, ws.sub_stream_id)
            if key in seen:
                raise ValueError(f"two weekly status entries for {key}")
            seen.add(key)

        return self

    # -- io ---------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Programme:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(self.model_dump_json())
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
