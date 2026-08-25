"""One representative spec per layout.

These back `deckpilot render-one`, which renders a single layout in isolation.
Working on the roadmap should not mean rebuilding twelve other slides first.
"""

from __future__ import annotations

from deckpilot.specgen.schema import (
    CharterColumn,
    SectionDividerSpec,
    WorkstreamCharterSpec,
)

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
}
