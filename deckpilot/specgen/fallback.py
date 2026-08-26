"""Deterministic deck specification, built straight from the programme data.

This is the path CI and the tests use, and the path `deckpilot demo` runs. It
needs no API key and produces the same deck every time for the same input.

It is also the reference for what the LLM path is allowed to change. The LLM
gets to choose which RAID items make a slide and how an action title is phrased.
It does not get to choose the deck's structure, the layouts, or anything about
position - all of which are decided here and below.
"""

from __future__ import annotations

from datetime import date

from deckpilot.data.models import RAG, Programme, RaidItem, Severity, SubStream, WorkPackage
from deckpilot.specgen.schema import (
    CharterColumn,
    DeckSpec,
    GanttBar,
    GanttMilestone,
    GanttRow,
    GovernanceBox,
    GovernanceChartSpec,
    GovernanceUnit,
    RoadmapGanttSpec,
    SectionDividerSpec,
    WorkstreamCharterSpec,
)

SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
RAG_ORDER = {RAG.RED: 0, RAG.AMBER: 1, RAG.GREEN: 2}
MIN_CHARTER_COLUMNS = 3  # the layout's own floor


# --------------------------------------------------------------------------
# Selection helpers
# --------------------------------------------------------------------------


def rank_raid(items: list[RaidItem]) -> list[RaidItem]:
    """Worst first: severity, then whichever is due soonest."""
    return sorted(items, key=lambda i: (SEVERITY_ORDER[i.severity], i.due))


def raid_for(programme: Programme, sub_stream_ids: set[str], limit: int) -> list[RaidItem]:
    return rank_raid([i for i in programme.raid if i.sub_stream_id in sub_stream_ids])[:limit]


def week_end(week: str) -> date:
    """The Friday of an ISO week.

    A report is made as at the end of its week, so that is where the reporting
    line belongs. Deriving it from the last achieved milestone instead - which an
    earlier version did - puts the line wherever the last milestone happened to
    fall, which is not the same thing and is wrong by days.
    """
    year, number = week.split("-W")
    return date.fromisocalendar(int(year), int(number), 5)


def _bullet(text: str) -> str:
    """Bullets do not take a terminal full stop; a mix of both looks careless."""
    return text.rstrip().rstrip(".")


def raid_line(item: RaidItem) -> str:
    """A RAID item as one line of annotation, not two."""
    return f"{item.title} ({item.severity.value}, {item.owner}, due {item.due:%d %b})"


def _worst(programme: Programme, week: str, sub_streams: list[SubStream]) -> tuple[RAG, str]:
    """The worst-rated sub-stream in a set, and its name."""
    ids = {ss.id for ss in sub_streams}
    reports = [s for s in programme.status_for_week(week) if s.sub_stream_id in ids]
    if not reports:
        return RAG.GREEN, sub_streams[0].name
    worst = min(reports, key=lambda s: (RAG_ORDER[s.rag], s.progress_pct))
    return worst.rag, programme.sub_stream(worst.sub_stream_id).name


# --------------------------------------------------------------------------
# Action titles
#
# Templated, but templated from the numbers rather than around them: a title
# that does not change when the position changes is not an action title.
# --------------------------------------------------------------------------


def charter_title(programme: Programme, week: str, wp: WorkPackage) -> str:
    ids = {ss.id for ss in wp.sub_streams}
    reports = [s for s in programme.status_for_week(week) if s.sub_stream_id in ids]
    total = len(reports) or len(wp.sub_streams)
    on_track = sum(1 for s in reports if s.rag is RAG.GREEN)
    rag, name = _worst(programme, week, wp.sub_streams)
    if on_track == total:
        return f"All {total} sub-streams are on track; the work package holds no critical path"
    if rag is RAG.RED:
        return f"{on_track} of {total} sub-streams are on track; {name} holds the critical path"
    return f"{on_track} of {total} sub-streams are on track; {name} needs a decision this month"


def roadmap_title(programme: Programme, week: str) -> str:
    upcoming = sorted(
        (g for g in programme.stage_gates if g.status.value != "passed"),
        key=lambda g: g.date,
    )
    reports = programme.status_for_week(week)
    behind = [
        programme.sub_stream(s.sub_stream_id).name for s in reports if s.rag is not RAG.GREEN
    ]
    if not upcoming:
        return "Every stage gate is passed; the programme is in steady state"
    gate = upcoming[0]
    if not behind:
        return f"Every work package completes into Gate {gate.number} on {gate.date:%d %B}"
    return (
        f"{len(reports) - len(behind)} of {len(reports)} sub-streams complete into "
        f"Gate {gate.number}; {len(behind)} do not"
    )


def governance_title(programme: Programme) -> str:
    return (
        f"Decision rights sit with the steering committee; delivery sits with "
        f"{len(programme.work_packages)} work packages"
    )


# --------------------------------------------------------------------------
# Slide builders
# --------------------------------------------------------------------------


def divider(number: int, title: str, kicker: str | None = None) -> SectionDividerSpec:
    return SectionDividerSpec(number=str(number), title=title, kicker=kicker)


def charter(programme: Programme, week: str, wp: WorkPackage) -> WorkstreamCharterSpec | None:
    """One slide per work package. A work package with fewer sub-streams than the
    layout's minimum gets no charter rather than a stretched one."""
    if len(wp.sub_streams) < MIN_CHARTER_COLUMNS:
        return None

    reports = {s.sub_stream_id: s for s in programme.status_for_week(week)}
    columns = []
    for i, ss in enumerate(wp.sub_streams, start=1):
        report = reports.get(ss.id)
        activities = [_bullet(a) for a in (report.activities if report else
                                           [p.name for p in ss.phases])]
        outcomes = [_bullet(ss.objective)]
        if report:
            outcomes.append(
                f"{report.progress_pct}% complete, rated {report.rag.value} at {week}"
            )
            if report.next_milestone_id:
                milestone = programme.milestone(report.next_milestone_id)
                outcomes.append(f"Next: {milestone.name} on {milestone.date:%d %b %Y}")
        columns.append(
            CharterColumn(
                number=f"{wp.number}.{i}",
                name=ss.name,
                activities=activities[:5],
                outcomes=outcomes[:4],
            )
        )

    ids = {ss.id for ss in wp.sub_streams}
    return WorkstreamCharterSpec(
        title=charter_title(programme, week, wp),
        subtitle=f"Work package {wp.number} - {wp.name} | Charter and current position",
        columns=columns,
        considerations=[raid_line(i) for i in raid_for(programme, ids, 4)],
    )


def roadmap(programme: Programme, week: str, today: date) -> RoadmapGanttSpec:
    rows = [
        GanttRow(
            work_package=wp.name,
            sub_stream=ss.name,
            bars=[
                GanttBar(label=p.name, start=p.start, end=p.end, status=p.status.value)
                for p in ss.phases
            ],
            milestones=[
                GanttMilestone(name=m.name, date=m.date, major=m.major)
                for m in programme.milestones
                if m.sub_stream_id == ss.id
            ],
        )
        for wp in programme.work_packages
        for ss in wp.sub_streams
    ]
    all_ids = {ss.id for ss in programme.sub_streams}
    return RoadmapGanttSpec(
        title=roadmap_title(programme, week),
        subtitle=(
            f"Programme roadmap | {programme.start:%B %Y} to {programme.end:%B %Y} | "
            f"Position as at week {week}"
        ),
        window_start=programme.start,
        window_end=programme.end,
        today=today,
        rows=rows,
        considerations=[raid_line(i) for i in raid_for(programme, all_ids, 4)],
    )


def governance(programme: Programme) -> GovernanceChartSpec:
    gov = programme.governance
    return GovernanceChartSpec(
        title=governance_title(programme),
        subtitle=f"Programme governance | {gov.pmo_cadence}",
        steering=GovernanceBox(
            title="Steering committee",
            caption=gov.steering_cadence,
            members=[f"{p.name} - {p.role}" for p in gov.steering_committee],
        ),
        programme_management=GovernanceBox(
            title="Programme management",
            caption=gov.pmo_cadence,
            members=[f"{p.name} - {p.role}" for p in gov.programme_management],
        ),
        units=[
            GovernanceUnit(
                number=str(wp.number),
                name=wp.name,
                core_team=[f"{t.name} ({t.note})" if t.note else t.name for t in wp.core_team],
                contributing_teams=[
                    f"{t.name} ({t.note})" if t.note else t.name for t in wp.contributing_teams
                ],
            )
            for wp in programme.work_packages
        ],
        considerations=gov.comments[:4],
    )


# --------------------------------------------------------------------------
# Deck
# --------------------------------------------------------------------------


def build_deck_spec(programme: Programme, week: str | None = None) -> DeckSpec:
    week = week or programme.weeks()[-1]
    if week not in programme.weeks():
        raise ValueError(
            f"no status reported for {week}; available weeks: {', '.join(programme.weeks())}"
        )
    today = min(max(week_end(week), programme.start), programme.end)

    slides: list = [
        divider(1, "Delivery plan", "Where the programme stands against its stage gates"),
        roadmap(programme, week, today),
        divider(2, "Governance", "Who decides, who delivers, and who has to be consulted"),
        governance(programme),
        divider(3, "Work packages", "Charter and current position for each work package"),
    ]
    slides += [c for c in (charter(programme, week, wp) for wp in programme.work_packages) if c]

    return DeckSpec(
        title=f"{programme.client} - {programme.name}",
        subtitle=programme.subtitle,
        week=week,
        slides=slides,
    )
