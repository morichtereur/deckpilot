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
from deckpilot.renderer.raid_table import paginate as raid_pagination
from deckpilot.specgen.schema import (
    AgendaEntry,
    AgendaSpec,
    BenefitRow,
    CharterColumn,
    CriteriaColumn,
    CriteriaColumnsSpec,
    DeckSpec,
    ExecSummarySpec,
    GanttBar,
    GanttMilestone,
    GanttRow,
    GovernanceBox,
    GovernanceChartSpec,
    GovernanceUnit,
    KeyMessage,
    KpiScorecardSpec,
    RaidRow,
    RaidTableSpec,
    RoadmapGanttSpec,
    SectionDividerSpec,
    StatusCard,
    StatusOverviewSpec,
    WorkstreamCharterSpec,
)
from deckpilot.theme import tokens as T

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


def _note(*paragraphs: str) -> str:
    """Speaker notes: what to say, and what you will be asked.

    Derived from the same figures as the slide, so the two cannot drift apart -
    which is the failure mode of notes written once and never updated.
    """
    return "\n\n".join(p for p in paragraphs if p)


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
    rag, worst_name = _worst(programme, week, wp.sub_streams)
    decisions = [
        _bullet(d)
        for report in programme.status_for_week(week)
        if report.sub_stream_id in ids
        for d in report.decisions_needed
    ]
    return WorkstreamCharterSpec(
        title=charter_title(programme, week, wp),
        subtitle=f"Work package {wp.number} - {wp.name} | Charter and current position",
        columns=columns,
        considerations=[raid_line(i) for i in raid_for(programme, ids, 4)],
        notes=_note(
            f"{wp.name} is led by {wp.lead}. The column to spend time on is "
            f"{worst_name}, rated {rag.value}.",
            f"Decisions this work package is asking for: {'; '.join(decisions)}."
            if decisions
            else "This work package is not asking for a decision today.",
            "The outcomes row is the charter commitment, not this week's position - "
            "the percentages under it are the position.",
        ),
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
        notes=_note(
            f"The vertical line is the reporting date, {week_end(week):%d %B}. "
            f"Everything left of it has happened.",
            "Red bars are the ones to talk to. Where a row shows two stacked bars the "
            "phases genuinely overlap - that is the constraint, not a drawing error.",
        ),
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
        notes=_note(
            f"Steering committee meets {gov.steering_cadence.lower()}; the programme "
            f"board runs {gov.pmo_cadence.lower()}.",
            "Use this slide only if the escalation path is questioned. Work package "
            "leads hold delegated authority; anything above that comes here.",
        ),
    )


def status_overview(programme: Programme, week: str) -> StatusOverviewSpec:
    """Roll the sub-stream reports up to one card per work package.

    A work package is rated by its worst sub-stream, not by an average: a package
    with one red stream is not amber.
    """
    reports = {s.sub_stream_id: s for s in programme.status_for_week(week)}
    cards = []
    for wp in programme.work_packages:
        members = [reports[ss.id] for ss in wp.sub_streams if ss.id in reports]
        if not members:
            continue
        worst = min(members, key=lambda s: (RAG_ORDER[s.rag], s.progress_pct))
        progress = round(sum(s.progress_pct for s in members) / len(members))
        upcoming = sorted(
            (
                programme.milestone(s.next_milestone_id)
                for s in members
                if s.next_milestone_id
            ),
            key=lambda m: m.date,
        )
        activities = [_bullet(s.headline) for s in sorted(members, key=lambda s: RAG_ORDER[s.rag])]
        cards.append(
            StatusCard(
                number=str(wp.number),
                name=wp.name,
                rag=worst.rag.value,
                progress_pct=progress,
                activities=activities[:3],
                next_milestone=(
                    f"{upcoming[0].name} on {upcoming[0].date:%d %b}" if upcoming else ""
                ),
            )
        )

    red = sum(1 for c in cards if c.rag == "red")
    amber = sum(1 for c in cards if c.rag == "amber")
    if red:
        verb = "is" if red == 1 else "are"
        title = (
            f"{red} of {len(cards)} work packages {verb} red; "
            f"the rest hold their gate dates"
        )
    elif amber:
        title = (
            f"{len(cards) - amber} of {len(cards)} work packages are on track; "
            f"{amber} need a decision"
        )
    else:
        title = f"All {len(cards)} work packages are on track"

    all_ids = {ss.id for ss in programme.sub_streams}
    worst_card = min(cards, key=lambda c: RAG_ORDER[RAG(c.rag)])
    notes = _note(
        f"A work package is rated by its worst sub-stream, not by an average - "
        f"{worst_card.name} is {worst_card.rag} on that basis even though it is "
        f"{worst_card.progress_pct}% complete overall.",
        "Walk the red and amber cards only. The green ones are on the slide so the "
        "committee can see they were looked at, not so they can be talked through.",
    )
    return StatusOverviewSpec(
        title=title,
        subtitle=f"Work package status | Week {week} | Rated by worst sub-stream",
        cards=cards,
        considerations=[raid_line(i) for i in raid_for(programme, all_ids, 4)],
        notes=notes,
    )


def raid_table(programme: Programme, week: str, per_type: int = 3) -> RaidTableSpec:
    """The most severe few of each type, not the whole log.

    A slide holding all eighteen items is a slide nobody reads; the rest belong
    in an appendix.
    """
    rows = []
    for kind in ("risk", "issue", "dependency", "assumption"):
        members = rank_raid([i for i in programme.raid if i.type.value == kind])[:per_type]
        rows += [_raid_row(item) for item in members]

    high = sum(1 for i in programme.raid if i.severity is Severity.HIGH)
    overdue = sum(1 for i in programme.raid if i.due < week_end(week))
    title = (
        f"{high} high-severity items are open, {overdue} of them past due"
        if overdue
        else f"{high} high-severity items are open, none yet past due"
    )
    owners = sorted({i.owner for i in programme.raid if i.severity is Severity.HIGH})
    return RaidTableSpec(
        title=title,
        subtitle=(
            f"RAID log | Week {week} | {len(rows)} of {len(programme.raid)} open items shown, "
            f"most severe of each type"
        ),
        rows=rows,
        notes=_note(
            f"{high} high-severity items are open across {len(owners)} owners: "
            f"{', '.join(owners)}.",
            "This slide shows the worst three of each type. The full log is in the "
            "appendix; do not read it out, point at it.",
        ),
    )


def kpi_scorecard(programme: Programme, week: str) -> KpiScorecardSpec | None:
    """Benefit measures against the delivery that is supposed to produce them."""
    if not programme.benefits:
        return None
    progress = {s.sub_stream_id: s.progress_pct for s in programme.status_for_week(week)}

    rows, behind = [], []
    for benefit in programme.benefits:
        expected = progress.get(benefit.sub_stream_id, 0) / 100
        rows.append(
            BenefitRow(
                name=benefit.display_name,
                owner=benefit.owner,
                baseline=benefit.plain(benefit.baseline),
                current=benefit.plain(benefit.current),
                target=benefit.plain(benefit.target),
                attainment=benefit.attainment,
                expected=expected,
            )
        )
        if benefit.attainment < expected:
            behind.append(benefit)

    ahead = len(rows) - len(behind)
    if not behind:
        title = f"All {len(rows)} measures are running ahead of the delivery behind them"
    else:
        worst = min(
            behind,
            key=lambda b: b.attainment - progress.get(b.sub_stream_id, 0) / 100,
        )
        title = (
            f"{ahead} of {len(rows)} measures are ahead of their delivery; "
            f"{worst.name.lower()} is the furthest adrift"
        )

    all_ids = {ss.id for ss in programme.sub_streams}
    lagging = ", ".join(b.name for b in behind[:3]) or "none"
    return KpiScorecardSpec(
        title=title,
        subtitle=(
            f"Benefit realisation | Week {week} | Measured against delivery progress, "
            f"not elapsed time, because benefits back-load"
        ),
        rows=rows,
        considerations=[raid_line(i) for i in raid_for(programme, all_ids, 3)],
        notes=_note(
            "The marker on each bar is the delivery progress of the stream producing "
            "that benefit. A bar short of its marker means the work has been done and "
            "the benefit has not followed.",
            f"Behind their delivery: {lagging}.",
            "If asked why this is not measured against the calendar: benefits "
            "back-load, so a calendar yardstick marks every measure late until the "
            "build lands, and tells you nothing you can act on.",
        ),
    )


def _raid_row(item: RaidItem) -> RaidRow:
    return RaidRow(
        id=item.id,
        kind=item.type.value,
        severity=item.severity.value,
        title=item.title,
        owner=item.owner,
        due=f"{item.due:%d %b}",
        mitigation=item.mitigation,
    )


def raid_appendix(programme: Programme, week: str) -> list[RaidTableSpec]:
    """The whole log, across as many slides as it takes.

    Pagination is measured, not guessed: the renderer reports how many rows fit
    at a readable size, and this emits one slide per page. Measurement stays in
    the layout because that is where the geometry is; how many slides result is a
    deck-structure decision, so it is made here.
    """
    rows = [_raid_row(i) for i in rank_raid(programme.raid)]
    pages = raid_pagination(rows, T.content_width(), T.content_height())

    high = sum(1 for i in programme.raid if i.severity is Severity.HIGH)
    title = (
        f"{high} of {len(programme.raid)} open items are high severity and "
        f"carry the programme's exposure"
    )
    return [
        RaidTableSpec(
            title=title,
            subtitle=(
                f"Full RAID log | Week {week} | Page {n} of {len(pages)} | "
                f"{len(programme.raid)} open items, worst first within each type"
            ),
            rows=page.rows,
            continued_groups=page.continued_groups,
            notes=_note(
                "Reference only. Do not present these slides; turn to them when an "
                "item is questioned.",
                f"Page {n} of {len(pages)} of the full log.",
            ),
        )
        for n, page in enumerate(pages, start=1)
    ]


def criteria_columns(programme: Programme, week: str) -> CriteriaColumnsSpec:
    """The stage gates, as a question each with the criteria that answer it."""
    today = week_end(week)
    columns = []
    for gate in sorted(programme.stage_gates, key=lambda g: g.date):
        state = gate.status.value if gate.status.value in ("passed", "at-risk") else "upcoming"
        columns.append(
            CriteriaColumn(
                question=f"Gate {gate.number}: {gate.name}",
                caption=f"{gate.date:%d %b %Y} - {gate.status.value}",
                characteristics=[_bullet(c) for c in gate.criteria],
                state=state,
            )
        )
    at_risk = [g for g in programme.stage_gates if g.status.value == "at-risk"]
    passed = [g for g in programme.stage_gates if g.status.value == "passed"]
    if at_risk:
        gate = min(at_risk, key=lambda g: g.date)
        title = (
            f"Gate {gate.number} on {gate.date:%d %B} is at risk; "
            f"the {len(passed)} gates behind it are passed"
        )
    else:
        title = (
            f"{len(passed)} of {len(programme.stage_gates)} gates are passed "
            f"and none are at risk"
        )
    return CriteriaColumnsSpec(
        title=title,
        subtitle=f"Stage gate criteria | Position as at week {week} ({today:%d %b %Y})",
        columns=columns,
        notes=_note(
            "Each column is a gate and the criteria it has to meet. Green columns are "
            "passed and closed.",
            (
                f"Spend the time on Gate {at_risk[0].number}: it is the only one at risk, "
                f"and the criteria listed under it are what a conditional pass would have "
                f"to waive."
                if at_risk
                else "No gate is currently at risk; this is for noting."
            ),
        ),
    )


def exec_summary(programme: Programme, week: str) -> ExecSummarySpec:
    """The verdict, the three things behind it, and what the meeting must decide.

    The title and the verdict say different things on purpose: the title states
    the so-what, the band quantifies the position. Repeating one sentence twice
    on the same slide reads as a bug.
    """
    reports = programme.status_for_week(week)
    red = [s for s in reports if s.rag is RAG.RED]
    amber = [s for s in reports if s.rag is RAG.AMBER]
    green = len(reports) - len(red) - len(amber)
    overall = "red" if red else ("amber" if amber else "green")

    next_gate = min(
        (g for g in programme.stage_gates if g.status.value != "passed"),
        key=lambda g: g.date,
        default=None,
    )
    gate_clause = ""
    if next_gate is not None:
        state = "is at risk" if next_gate.status.value == "at-risk" else "is on track"
        gate_clause = f" Gate {next_gate.number} on {next_gate.date:%d %B} {state}."

    verdict = (
        f"{green} of {len(reports)} sub-streams on track, "
        f"{len(amber)} amber, {len(red)} red.{gate_clause}"
    )

    if red:
        worst = programme.sub_stream(red[0].sub_stream_id).name
        title = (
            f"{worst} is red and holds Gate {next_gate.number}"
            if next_gate is not None
            else f"{worst} is red"
        )
        if len(reports) - len(red) > 0:
            title += f"; the other {len(reports) - len(red)} sub-streams clear it"
    elif amber:
        title = (
            f"{green} of {len(reports)} sub-streams are on track; "
            f"{len(amber)} need a decision this month"
        )
    else:
        title = f"All {len(reports)} sub-streams are on track and no gate is at risk"

    messages = []
    for report in sorted(reports, key=lambda s: (RAG_ORDER[s.rag], s.progress_pct))[:3]:
        sub_stream = programme.sub_stream(report.sub_stream_id)
        messages.append(
            KeyMessage(
                heading=sub_stream.name,
                detail=f"{_bullet(report.headline)}. {report.progress_pct}% complete.",
                rag=report.rag.value,
            )
        )

    decisions = [_bullet(d) for report in reports for d in report.decisions_needed]
    worst_names = ", ".join(
        programme.sub_stream(r.sub_stream_id).name for r in (red + amber)[:3]
    )
    notes = _note(
        f"Open on the verdict: {verdict}",
        (
            f"The exposure sits in {worst_names}. "
            f"Take the decisions in order - the first two are the ones that move Gate "
            f"{next_gate.number} if they are taken this month."
            if decisions and next_gate is not None
            else "There is nothing to decide today; this is for noting."
        ),
        (
            "Expect to be challenged on whether the gate can hold with a conditional "
            "pass. The answer is in the appendix: the high-severity items and their "
            "owners are listed there with dates."
        ),
    )
    return ExecSummarySpec(
        title=title,
        subtitle=f"{programme.client} - {programme.name} | Executive summary | Week {week}",
        overall_rag=overall,
        verdict=verdict,
        messages=messages,
        decisions=decisions[:4],
        notes=notes,
    )


# --------------------------------------------------------------------------
# Deck
# --------------------------------------------------------------------------


def agenda(body: list, programme: Programme, week: str, offset: int) -> AgendaSpec:
    """Contents, with the page each section actually starts on.

    `offset` is how many slides precede the body - the executive summary and this
    contents page itself. The numbers can only be worked out once the body is
    complete, which because the appendix is paginated by measurement means after
    the renderer has said how many slides the RAID log needs.
    """
    entries = [
        AgendaEntry(
            number=slide.number,
            title=slide.title,
            caption=slide.kicker,
            page=offset + index + 1,
        )
        for index, slide in enumerate(body)
        if slide.layout == "section_divider"
    ]
    return AgendaSpec(
        title="Contents",
        subtitle=(
            f"{programme.client} - {programme.name} | Week {week} | "
            f"{offset + len(body)} slides"
        ),
        entries=entries,
    )


def build_deck_spec(programme: Programme, week: str | None = None) -> DeckSpec:
    week = week or programme.weeks()[-1]
    if week not in programme.weeks():
        raise ValueError(
            f"no status reported for {week}; available weeks: {', '.join(programme.weeks())}"
        )
    today = min(max(week_end(week), programme.start), programme.end)

    body: list = [
        divider(1, "Where we stand", "Work package status and the open RAID position"),
        status_overview(programme, week),
        raid_table(programme, week),
        kpi_scorecard(programme, week),
        divider(2, "Delivery plan", "The roadmap and the gates it has to clear"),
        roadmap(programme, week, today),
        criteria_columns(programme, week),
        divider(3, "Work packages", "Charter and current position for each work package"),
    ]
    body = [slide for slide in body if slide is not None]
    body += [c for c in (charter(programme, week, wp) for wp in programme.work_packages) if c]
    body += [
        divider(4, "Governance", "Who decides, who delivers, and who has to be consulted"),
        governance(programme),
        divider(5, "Appendix", "The full RAID log, in support of the position above"),
    ]
    body += raid_appendix(programme, week)

    summary = exec_summary(programme, week)
    # The executive summary and the contents page sit ahead of the body, so the
    # body's first slide is page 3.
    slides = [summary, agenda(body, programme, week, offset=2), *body]

    return DeckSpec(
        title=f"{programme.client} - {programme.name}",
        subtitle=programme.subtitle,
        week=week,
        slides=slides,
    )
