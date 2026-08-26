"""One representative spec per layout.

These back `deckpilot render-one`, which renders a single layout in isolation.
Working on the roadmap should not mean rebuilding twelve other slides first.
"""

from __future__ import annotations

from datetime import date

from deckpilot.data.generate import build_programme
from deckpilot.specgen import fallback
from deckpilot.specgen.schema import (
    CharterColumn,
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


def _roadmap_sample() -> RoadmapGanttSpec:
    """The roadmap is built from the real programme: hand-writing twelve rows of
    phases and milestones would drift out of step with the data the moment either
    changed."""
    programme = build_programme()
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
    return RoadmapGanttSpec(
        title="Build completes into Gate 3 for three work packages; P2P and master data do not",
        subtitle=(
            "Programme roadmap | February 2026 to January 2027 | Position as at week 2026-W35"
        ),
        window_start=programme.start,
        window_end=programme.end,
        today=date(2026, 8, 26),
        rows=rows,
        considerations=[
            "Gate 3 on 11 September is the binding date for P2P build and the control framework",
            "Master data cleansing must freeze on 9 October or migration validation cannot start",
            "Migration waves 2 and 3 overlap by seven weeks against single-wave trainer capacity",
            "The global cutover is a single weekend, with rollback feasible for 18 hours only",
        ],
    )

def _governance_sample() -> GovernanceChartSpec:
    programme = build_programme()
    gov = programme.governance
    return GovernanceChartSpec(
        title="Decision rights sit with the steering committee; delivery sits with four work packages",
        subtitle="Programme governance | Escalation runs weekly through the programme board",
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
                core_team=[
                    f"{t.name} ({t.note})" if t.note else t.name for t in wp.core_team
                ],
                contributing_teams=[
                    f"{t.name} ({t.note})" if t.note else t.name
                    for t in wp.contributing_teams
                ],
            )
            for wp in programme.work_packages
        ],
        considerations=gov.comments[:4],
    )


def _from_programme(builder) -> object:
    """v2 layouts take their sample straight from the deterministic builder.

    Hand-writing a second copy of a status card or a RAID row only creates
    something that drifts out of step with the data the moment either changes.
    """
    programme = build_programme()
    return builder(programme, programme.weeks()[-1])


SAMPLES: dict[str, object] = {
    "section_divider": SectionDividerSpec(
        number="2",
        title="Process standardisation",
        kicker="Four end-to-end processes, one global standard, one control framework",
    ),
    "workstream_charter": WorkstreamCharterSpec(
        title="Three of four processes are on standard; P2P holds the critical path",
        subtitle="Work package 2 - Process Standardisation | Charter and current position",
        columns=[
            CharterColumn(
                number="2.1",
                name="Record to Report",
                activities=[
                    "Standardise the close calendar to a 5+2 day cycle across all five regions",
                    "Reduce the journal taxonomy from 214 entry types to 61",
                    "Rebuild the close control set and walk it through with External Audit",
                    "Run a pilot close on the October cycle before global rollout",
                ],
                outcomes=[
                    "One close calendar and one journal taxonomy group-wide",
                    "Control framework accepted by External Audit at Gate 3",
                ],
            ),
            CharterColumn(
                number="2.2",
                name="Purchase to Pay",
                activities=[
                    "Lock a single three-way match tolerance policy across all regions",
                    "Configure the Italy, Spain and Poland e-invoicing variants with Group Tax",
                    "Simplify the approval matrix from nine levels to four",
                    "Design supplier master de-duplication with the master data sub-stream",
                ],
                outcomes=[
                    "Touchless invoice rate from 41% to 75% by hypercare exit",
                    "One supplier master with governed onboarding",
                ],
            ),
            CharterColumn(
                number="2.3",
                name="Order to Cash",
                activities=[
                    "Agree one dunning policy with the five regional credit committees",
                    "Design cash application matching rules with Treasury",
                    "Consolidate billing for the two legacy entities",
                    "Segment collections by customer value and payment behaviour",
                ],
                outcomes=[
                    "DSO from a 54-day baseline to 47 days",
                    "One dunning policy and one disputes workflow",
                ],
            ),
            CharterColumn(
                number="2.4",
                name="Master Data & Controls",
                activities=[
                    "Publish a governed data model for vendor, customer and chart of accounts",
                    "Cleanse the legacy vendor master against the new validation rules",
                    "Stand up data stewardship with named owners per domain",
                    "Build duplicate detection with the platform team",
                ],
                outcomes=[
                    "Vendor master validation pass rate from 77% to 98%",
                    "Named stewardship in place before the migration cut-off",
                ],
            ),
        ],
        considerations=[
            "P2P country tax variants were underestimated at design and now hold the Gate 3 date",
            "Legacy vendor data quality is materially worse than the design assumption of 8%",
            "Regional finance capacity for UAT overlaps the year-end close",
            "Two intercompany routing decisions closed at Gate 2 have been reopened",
        ],
    ),
    "roadmap_gantt": _roadmap_sample(),
    "governance_chart": _governance_sample(),
    "exec_summary": _from_programme(fallback.exec_summary),
    "status_overview": _from_programme(fallback.status_overview),
    "raid_table": _from_programme(fallback.raid_table),
    "criteria_columns": _from_programme(fallback.criteria_columns),
}
