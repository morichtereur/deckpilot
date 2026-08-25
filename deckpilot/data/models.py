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
