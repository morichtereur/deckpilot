"""Build the synthetic Northwind GBS programme dataset.

Everything here is fictional. The data is hand-authored rather than randomised:
a status deck is only convincing if the RAID log argues with the roadmap and the
weekly reports argue with both, and random generators do not produce that.

The one thing that *is* derived is history. Each sub-stream declares its current
week honestly; earlier weeks are walked backwards from it, so progress never goes
up as you go back in time and the activity mix rotates the way a real report does.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from deckpilot.data.models import (
    RAG,
    BenefitDirection,
    BenefitMeasure,
    GateStatus,
    Governance,
    Milestone,
    MilestoneStatus,
    Person,
    Phase,
    PhaseStatus,
    Programme,
    RaidItem,
    RaidType,
    Severity,
    StageGate,
    SubStream,
    Team,
    WeeklyStatus,
    WorkPackage,
)

PROGRAMME_START = date(2026, 2, 2)
PROGRAMME_END = date(2027, 1, 29)
AS_OF = date(2026, 8, 26)
HISTORY_WEEKS = 4


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _phase_status(start: date, end: date, as_of: date, at_risk: bool = False) -> PhaseStatus:
    if at_risk:
        return PhaseStatus.AT_RISK
    if end < as_of:
        return PhaseStatus.COMPLETE
    if start <= as_of <= end:
        return PhaseStatus.IN_PROGRESS
    return PhaseStatus.PLANNED


# --------------------------------------------------------------------------
# Work packages and sub-streams
#
# Each sub-stream entry is:
#   id, name, lead, objective,
#   phases      -> (label, start, end, at_risk)
#   activities  -> the pool the weekly report draws from, newest first
#   current     -> (rag, progress %, headline)
#   decisions   -> decisions the sub-stream is putting to the steering committee
# --------------------------------------------------------------------------

WORK_PACKAGES: list[dict] = [
    {
        "id": "wp1",
        "number": 1,
        "name": "Operating Model & Service Design",
        "lead": "Ines Vogelsang",
        "objective": (
            "Define the target service portfolio, the organisation that delivers it and the "
            "footprint it runs from, so that process and technology design have a fixed frame."
        ),
        "core_team": [
            ("GBS Design Office", "8 FTE, dedicated"),
            ("Finance Operating Model", "4 FTE, dedicated"),
            ("HR Organisation Design", "2 FTE, 50% allocation"),
        ],
        "contributing": [
            ("Group Finance Policy", None),
            ("Regional Controllers (5)", "consulted per region"),
            ("Workplace & Real Estate", None),
            ("Legal & Employee Relations", None),
        ],
        "sub_streams": [
            {
                "id": "ss11",
                "name": "Service Catalogue & SLAs",
                "lead": "Ines Vogelsang",
                "objective": "A costed catalogue of 46 services with agreed SLAs and a KPI baseline.",
                "phases": [
                    ("Service definition", "2026-02-09", "2026-04-24", False),
                    ("SLA negotiation", "2026-04-27", "2026-07-31", False),
                    ("Catalogue publication", "2026-08-03", "2026-10-16", False),
                    ("Embed in service reviews", "2026-10-19", "2027-01-22", False),
                ],
                "activities": [
                    "Published catalogue v1.2 covering all 46 services with owner, SLA and unit cost",
                    "Closed the last four SLA exceptions with the Nordics and Brazil controllers",
                    "Agreed the KPI baseline set (14 measures) with Group Finance Policy",
                    "Ran the service-review dry run with the WP2 process owners",
                    "Reconciled catalogue scope against the WP4 migration waves",
                    "Costed the catalogue against the FY26 GBS budget with Finance Operating Model",
                    "Walked the escalation model through with Regional Controllers",
                ],
                "current": (RAG.GREEN, 78, "Catalogue signed off in all five regions; focus moves to embedding SLAs in the service review"),
                "decisions": [],
            },
            {
                "id": "ss12",
                "name": "Organisation & Role Design",
                "lead": "Tobias Lindqvist",
                "objective": "Target structure, role profiles and span-of-control model for 640 GBS roles.",
                "phases": [
                    ("Role architecture", "2026-02-09", "2026-05-08", False),
                    ("Structure & spans", "2026-05-11", "2026-08-14", False),
                    ("Consultation & selection", "2026-08-17", "2026-11-20", True),
                    ("Appointment & onboarding", "2026-11-23", "2027-01-29", False),
                ],
                "activities": [
                    "Completed role profiles for all 640 target roles and banded them with HR",
                    "Opened works council consultation in Germany and the Netherlands",
                    "Modelled three span-of-control scenarios for the hub leadership layer",
                    "Mapped 512 of 640 incumbents to target roles; 128 remain unresolved",
                    "Agreed the retention framework for 34 critical knowledge holders",
                    "Briefed regional HR leads on the selection process and timetable",
                    "Aligned role families with the WP2 process taxonomy",
                ],
                "current": (RAG.AMBER, 61, "Works council consultation started two weeks late; selection window is now the binding constraint on Gate 4"),
                "decisions": [
                    "Approve the retention framework for 34 critical knowledge holders before selection opens",
                    "Confirm whether the German consultation timetable may run in parallel with Dutch selection",
                ],
            },
            {
                "id": "ss13",
                "name": "Location & Footprint Strategy",
                "lead": "Priya Raghunathan",
                "objective": "Confirm the two-hub-plus-nearshore footprint and secure the site build-out.",
                "phases": [
                    ("Location assessment", "2026-02-16", "2026-05-22", False),
                    ("Site selection & business case", "2026-05-25", "2026-08-07", False),
                    ("Site build-out", "2026-08-10", "2026-12-18", False),
                ],
                "activities": [
                    "Signed the Krakow lease; fit-out contractor mobilised on site",
                    "Closed the Kuala Lumpur headcount ramp plan with Workplace & Real Estate",
                    "Refreshed the footprint business case with actual salary benchmarks",
                    "Confirmed nearshore Bogota as the Americas coverage option",
                    "Agreed the desk-ratio assumption at 1.4 with Workplace",
                    "Completed the labour-market risk review for both hubs",
                ],
                "current": (RAG.GREEN, 72, "Both hubs contracted on plan; Krakow fit-out is the only remaining critical path item"),
                "decisions": [],
            },
        ],
    },
    {
        "id": "wp2",
        "number": 2,
        "name": "Process Standardisation",
        "lead": "Marcus Adeyemi",
        "objective": (
            "Move four end-to-end finance processes onto a single global standard with a "
            "documented control framework, so the hubs inherit one way of working, not five."
        ),
        "core_team": [
            ("Global Process Owners (4)", "1 per E2E process"),
            ("Process Design Team", "11 FTE, dedicated"),
            ("Internal Controls", "3 FTE, dedicated"),
        ],
        "contributing": [
            ("Regional Finance Teams", "design workshops + UAT"),
            ("Group Tax", "P2P and O2C tax logic"),
            ("Treasury", "O2C cash application"),
            ("External Audit", "control framework review"),
        ],
        "sub_streams": [
            {
                "id": "ss21",
                "name": "Record to Report",
                "lead": "Marcus Adeyemi",
                "objective": "One global close calendar, standard journal taxonomy and a rebuilt control set.",
                "phases": [
                    ("Process design", "2026-02-16", "2026-05-29", False),
                    ("Control framework build", "2026-06-01", "2026-09-11", False),
                    ("Test & pilot close", "2026-09-14", "2026-11-27", False),
                    ("Global rollout", "2026-11-30", "2027-01-29", False),
                ],
                "activities": [
                    "Standardised the close calendar to a 5+2 day cycle across all five regions",
                    "Rebuilt the journal taxonomy; 214 entry types reduced to 61",
                    "Completed control design for the close cycle and walked it through with External Audit",
                    "Agreed the account reconciliation threshold policy with Internal Controls",
                    "Dry-ran the pilot close scenario with the Nordics team",
                    "Mapped the flux analysis process onto the WP3 reporting layer",
                    "Closed 18 of 23 design decisions logged at Gate 2",
                ],
                "current": (RAG.GREEN, 74, "Control framework on track for Gate 3; pilot close scheduled for the October cycle"),
                "decisions": [],
            },
            {
                "id": "ss22",
                "name": "Purchase to Pay",
                "lead": "Chiara Bellandi",
                "objective": "Single P2P flow with touchless invoice processing and one supplier master.",
                "phases": [
                    ("Process design", "2026-02-16", "2026-05-29", False),
                    ("Build & configuration", "2026-06-01", "2026-09-25", True),
                    ("Test & UAT", "2026-09-28", "2026-12-11", False),
                    ("Global rollout", "2026-12-14", "2027-01-29", False),
                ],
                "activities": [
                    "Locked the three-way match tolerance policy across all regions",
                    "Reworked the invoice exception taxonomy after the tax logic finding",
                    "Rebuilt the Italy and Spain e-invoicing variants with Group Tax",
                    "Completed supplier master de-duplication design with WP2 Master Data",
                    "Held the touchless-rate baseline review; current global rate 41%",
                    "Agreed the approval matrix simplification from 9 levels to 4",
                    "Reopened two design decisions on intercompany invoice routing",
                ],
                "current": (RAG.RED, 52, "Country tax variants were underestimated at design; build slips past Gate 3 without additional Group Tax capacity"),
                "decisions": [
                    "Release two additional Group Tax analysts to P2P through October",
                    "Accept a Gate 3 conditional pass for P2P, or move the gate for all of WP2",
                ],
            },
            {
                "id": "ss23",
                "name": "Order to Cash",
                "lead": "Daniel Okonkwo",
                "objective": "Standard billing, collections and cash application with one dunning policy.",
                "phases": [
                    ("Process design", "2026-03-02", "2026-06-12", False),
                    ("Build & configuration", "2026-06-15", "2026-09-25", False),
                    ("Test & UAT", "2026-09-28", "2026-12-11", False),
                    ("Global rollout", "2026-12-14", "2027-01-29", False),
                ],
                "activities": [
                    "Agreed a single dunning policy with the five regional credit committees",
                    "Designed the cash application matching rules with Treasury",
                    "Completed the billing consolidation design for the two legacy entities",
                    "Baselined DSO at 54 days as the benefit measurement start point",
                    "Closed the disputed-invoice workflow design with WP3",
                    "Ran the collections segmentation workshop with regional teams",
                ],
                "current": (RAG.GREEN, 68, "Design closed on plan; build tracking to Gate 3 with no open dependencies"),
                "decisions": [],
            },
            {
                "id": "ss24",
                "name": "Master Data & Controls",
                "lead": "Anneke de Vries",
                "objective": "One governed master data model for vendor, customer and chart of accounts.",
                "phases": [
                    ("Data model design", "2026-03-02", "2026-06-26", False),
                    ("Cleansing & governance build", "2026-06-29", "2026-10-09", True),
                    ("Migration validation", "2026-10-12", "2027-01-08", False),
                ],
                "activities": [
                    "Published the governed data model for vendor, customer and chart of accounts",
                    "Profiled the legacy vendor master; 23% of records fail the new validation rules",
                    "Stood up the data stewardship model with named owners per domain",
                    "Agreed the cleansing cut-off date with WP4 migration planning",
                    "Built the duplicate-detection ruleset with the WP3 platform team",
                    "Escalated the cleansing resourcing gap to the programme board",
                ],
                "current": (RAG.AMBER, 57, "Legacy data quality is worse than assumed at design; cleansing needs three more stewards to hold the WP4 cut-off"),
                "decisions": [
                    "Fund three additional data stewards through the cleansing window to protect the migration cut-off",
                ],
            },
        ],
    },
    {
        "id": "wp3",
        "number": 3,
        "name": "Technology & Automation",
        "lead": "Rahul Menon",
        "objective": (
            "Deliver the platform the standard processes run on: one ERP template, a workflow "
            "and automation layer, and reporting that the service reviews can be run from."
        ),
        "core_team": [
            ("ERP Template Team", "9 FTE, dedicated"),
            ("Automation CoE", "5 FTE, dedicated"),
            ("Data & Analytics", "4 FTE, dedicated"),
        ],
        "contributing": [
            ("Group IT Architecture", "design authority"),
            ("Information Security", "gated reviews"),
            ("Platform Vendor", "statement of work"),
            ("Regional IT (5)", "cutover support"),
        ],
        "sub_streams": [
            {
                "id": "ss31",
                "name": "ERP Template Alignment",
                "lead": "Rahul Menon",
                "objective": "Collapse four regional ERP variants onto one global template.",
                "phases": [
                    ("Template gap analysis", "2026-02-09", "2026-05-15", False),
                    ("Template build", "2026-05-18", "2026-09-11", False),
                    ("Integration test", "2026-09-14", "2026-12-04", False),
                    ("Cutover & hypercare", "2026-12-07", "2027-01-29", False),
                ],
                "activities": [
                    "Closed 96 of 118 template gaps; the remainder are localisation-only",
                    "Passed the Group IT Architecture design authority review",
                    "Completed the chart of accounts alignment with WP2 Master Data",
                    "Built the interface inventory for the 31 downstream systems",
                    "Agreed the regression test scope with Regional IT",
                    "Confirmed the cutover approach as a single global weekend",
                ],
                "current": (RAG.GREEN, 71, "Template build completes into Gate 3; integration test scope agreed with all five regions"),
                "decisions": [],
            },
            {
                "id": "ss32",
                "name": "Workflow & Intelligent Automation",
                "lead": "Sofia Marchetti",
                "objective": "Automate 38 candidate steps across P2P, O2C and R2R with a governed pipeline.",
                "phases": [
                    ("Opportunity assessment", "2026-03-16", "2026-06-19", False),
                    ("Automation build wave 1", "2026-06-22", "2026-10-02", False),
                    ("Automation build wave 2", "2026-10-05", "2027-01-15", False),
                ],
                "activities": [
                    "Delivered 11 of 18 wave 1 automations into the pre-production environment",
                    "Passed the Information Security review for the document extraction service",
                    "Re-scoped four P2P automations pending the tax variant rework",
                    "Established the automation change-control process with the Automation CoE",
                    "Measured wave 1 benefit at 6.2 FTE against a 7.0 FTE plan",
                    "Built the exception-handling pattern reused across all workflow automations",
                ],
                "current": (RAG.AMBER, 55, "Wave 1 is four automations behind because P2P design reopened; wave 2 scope is protected"),
                "decisions": [
                    "Confirm whether the four re-scoped P2P automations move to wave 2 or drop from scope",
                ],
            },
            {
                "id": "ss33",
                "name": "Reporting & Analytics",
                "lead": "Jonas Brenner",
                "objective": "One performance layer: SLA, KPI and cost-to-serve reporting for the service reviews.",
                "phases": [
                    ("Reporting design", "2026-04-06", "2026-07-17", False),
                    ("Data layer build", "2026-07-20", "2026-11-06", False),
                    ("Dashboard build & UAT", "2026-11-09", "2027-01-22", False),
                ],
                "activities": [
                    "Signed off the reporting design against the WP1 KPI baseline",
                    "Built the cost-to-serve model down to service level",
                    "Stood up the data layer for SLA measurement in the test environment",
                    "Agreed the single source of truth for headcount with HR Organisation Design",
                    "Completed the reporting requirements review with Regional Controllers",
                ],
                "current": (RAG.GREEN, 48, "Design signed off against the KPI baseline; data layer build started on plan"),
                "decisions": [],
            },
        ],
    },
    {
        "id": "wp4",
        "number": 4,
        "name": "Transition & Change",
        "lead": "Yusuf Demirci",
        "objective": (
            "Move the work to the hubs without losing it: structured knowledge transfer in "
            "three waves, with the change and training effort sized to the same waves."
        ),
        "core_team": [
            ("Transition Management Office", "6 FTE, dedicated"),
            ("Change & Communications", "4 FTE, dedicated"),
            ("Training Design", "3 FTE, dedicated"),
        ],
        "contributing": [
            ("Retained Finance Leads (5)", "wave sign-off"),
            ("Hub Operations Leadership", None),
            ("Legal & Employee Relations", None),
            ("Internal Communications", None),
        ],
        "sub_streams": [
            {
                "id": "ss41",
                "name": "Knowledge Transfer & Migration",
                "lead": "Yusuf Demirci",
                "objective": "Three migration waves covering 640 roles, each gated on a stability review.",
                "phases": [
                    ("Wave planning", "2026-04-06", "2026-07-24", False),
                    ("Wave 1 knowledge transfer", "2026-07-27", "2026-10-30", False),
                    ("Wave 2 knowledge transfer", "2026-10-05", "2026-12-18", False),
                    ("Wave 3 knowledge transfer", "2026-11-30", "2027-01-29", False),
                ],
                "activities": [
                    "Started wave 1 knowledge transfer for R2R and O2C in Krakow",
                    "Completed process documentation for 71 of 94 wave 1 activities",
                    "Agreed the wave stability criteria with Retained Finance Leads",
                    "Built the shadow-and-reverse-shadow schedule for wave 1",
                    "Confirmed the wave 2 scope against the WP2 rollout sequence",
                    "Flagged the wave 2 / wave 3 overlap as a capacity risk to the TMO",
                ],
                "current": (RAG.AMBER, 44, "Wave 1 started on time, but wave 2 and 3 now overlap by seven weeks and hub trainer capacity is the constraint"),
                "decisions": [
                    "Approve contract trainer capacity for the wave 2 and 3 overlap, or resequence wave 3",
                ],
            },
            {
                "id": "ss42",
                "name": "Change, Comms & Training",
                "lead": "Laura Nkemelu",
                "objective": "Readiness for 640 movers and 1,200 retained users, measured not assumed.",
                "phases": [
                    ("Change impact assessment", "2026-03-16", "2026-06-26", False),
                    ("Curriculum build", "2026-06-29", "2026-10-23", False),
                    ("Delivery & readiness", "2026-10-26", "2027-01-29", False),
                ],
                "activities": [
                    "Completed the change impact assessment across all five regions",
                    "Built 14 of 22 curriculum modules against the WP2 process designs",
                    "Ran the second pulse survey; readiness index at 62, up from 54",
                    "Aligned the communications calendar with the consultation timetable",
                    "Trained the first cohort of 18 change champions",
                    "Reworked three modules after the P2P design reopened",
                ],
                "current": (RAG.GREEN, 53, "Curriculum build tracking to plan; readiness index improving ahead of the wave 1 go-live"),
                "decisions": [],
            },
        ],
    },
]

STAGE_GATES = [
    ("g1", 1, "Mobilisation complete", "2026-03-13", GateStatus.PASSED, [
        "Programme team mobilised and funded",
        "Baseline scope and benefit case approved",
        "Governance and cadence in place",
    ]),
    ("g2", 2, "Design sign-off", "2026-05-29", GateStatus.PASSED, [
        "End-to-end process designs approved by all Global Process Owners",
        "Target operating model and role architecture agreed",
        "Design decision log closed or dispositioned",
    ]),
    ("g3", 3, "Build complete", "2026-09-11", GateStatus.AT_RISK, [
        "ERP template build complete and unit tested",
        "Control framework built and walked through with External Audit",
        "P2P country tax variants configured",
        "Wave 1 automations in pre-production",
    ]),
    ("g4", 4, "Go-live readiness", "2026-11-20", GateStatus.UPCOMING, [
        "Integration and user acceptance testing signed off",
        "Wave 1 knowledge transfer complete and stability review passed",
        "Selection complete and hub roles appointed",
        "Cutover and fallback plans rehearsed",
    ]),
    ("g5", 5, "Hypercare exit", "2027-01-22", GateStatus.UPCOMING, [
        "All three waves live and stable for four consecutive weeks",
        "SLAs met for two consecutive service review cycles",
        "Benefit run-rate tracking within 10% of the case",
    ]),
]

# id, type, title, description, severity, owner, raised, due, mitigation, sub-stream
RAID = [
    ("R-01", RaidType.RISK, "P2P country tax variants exceed design assumption",
     "Italy, Spain and Poland e-invoicing variants each need bespoke configuration that the "
     "design assumed would be template-standard, putting the Gate 3 build date at risk.",
     Severity.HIGH, "Chiara Bellandi", "2026-07-13", "2026-09-11",
     "Two Group Tax analysts released to P2P through October; conditional Gate 3 pass proposed for P2P only.",
     "ss22"),
    ("R-02", RaidType.RISK, "Works council consultation extends the selection window",
     "German and Dutch consultation opened two weeks late. Any further slip compresses selection "
     "and appointment into the Gate 4 window with no float.",
     Severity.HIGH, "Tobias Lindqvist", "2026-08-10", "2026-11-20",
     "Weekly tracking with Legal & Employee Relations; parallel-running Dutch selection under review.",
     "ss12"),
    ("R-03", RaidType.RISK, "Hub trainer capacity constrains overlapping migration waves",
     "Waves 2 and 3 now overlap by seven weeks. Hub trainer capacity supports one wave at a time "
     "without contract support.",
     Severity.HIGH, "Yusuf Demirci", "2026-08-17", "2026-10-05",
     "Contract trainer capacity costed and put to the steering committee; resequencing wave 3 held as fallback.",
     "ss41"),
    ("R-04", RaidType.RISK, "Legacy vendor data quality below the migration threshold",
     "23% of legacy vendor records fail the new validation rules against an assumed 8%, "
     "threatening the WP4 cleansing cut-off.",
     Severity.HIGH, "Anneke de Vries", "2026-07-27", "2026-10-09",
     "Three additional data stewards requested; automated duplicate detection brought forward.",
     "ss24"),
    ("R-05", RaidType.RISK, "Retention of critical knowledge holders through selection",
     "34 incumbents hold undocumented process knowledge and sit in scope for selection. "
     "Attrition before knowledge transfer would be unrecoverable within the plan.",
     Severity.MEDIUM, "Tobias Lindqvist", "2026-06-15", "2026-10-30",
     "Retention framework drafted with HR; knowledge capture prioritised for the 34 named roles.",
     "ss12"),
    ("R-06", RaidType.RISK, "Single global cutover weekend leaves no fallback window",
     "The agreed cutover approach concentrates all five regions into one weekend, "
     "with rollback feasible only in the first 18 hours.",
     Severity.MEDIUM, "Rahul Menon", "2026-08-03", "2026-12-04",
     "Two full cutover rehearsals scheduled; go / no-go checkpoint set at hour 12.",
     "ss31"),
    ("I-01", RaidType.ISSUE, "Wave 1 automation delivery four items behind plan",
     "11 of 18 wave 1 automations are in pre-production against a plan of 15, because "
     "four P2P automations were re-scoped when the P2P design reopened.",
     Severity.MEDIUM, "Sofia Marchetti", "2026-08-10", "2026-10-02",
     "Four automations proposed for wave 2; wave 1 benefit shortfall of 0.8 FTE accepted.",
     "ss32"),
    ("I-02", RaidType.ISSUE, "Intercompany invoice routing design reopened",
     "Two design decisions closed at Gate 2 were reopened after the tax variant finding, "
     "leaving the intercompany routing rules unconfirmed.",
     Severity.MEDIUM, "Chiara Bellandi", "2026-08-17", "2026-09-18",
     "Decision paper to the Global Process Owner forum on 2026-09-04.",
     "ss22"),
    ("I-03", RaidType.ISSUE, "Three training modules require rework",
     "Three of 22 curriculum modules were built against the superseded P2P design "
     "and must be rebuilt before the wave 1 delivery window.",
     Severity.LOW, "Laura Nkemelu", "2026-08-17", "2026-10-23",
     "Rework scheduled into the September sprint; no impact on the delivery start date.",
     "ss42"),
    ("I-04", RaidType.ISSUE, "128 incumbents not yet mapped to target roles",
     "512 of 640 incumbents are mapped. The unmapped population is concentrated in "
     "the two regions where consultation has not yet opened.",
     Severity.MEDIUM, "Tobias Lindqvist", "2026-08-03", "2026-09-25",
     "Regional HR leads to complete mapping ahead of consultation opening in each region.",
     "ss12"),
    ("D-01", RaidType.DEPENDENCY, "Group Tax capacity for P2P country variants",
     "P2P build completion depends on two Group Tax analysts being available through October. "
     "Group Tax is concurrently supporting the statutory reporting change.",
     Severity.HIGH, "Marcus Adeyemi", "2026-07-20", "2026-09-04",
     "Steering committee decision requested; Group Tax lead has confirmed availability in principle.",
     "ss22"),
    ("D-02", RaidType.DEPENDENCY, "Krakow fit-out completion gates wave 1 onboarding",
     "Wave 1 hub onboarding cannot start before the Krakow fit-out hands over. "
     "Handover is planned for 2026-10-16 against a wave 1 need date of 2026-10-26.",
     Severity.MEDIUM, "Priya Raghunathan", "2026-06-29", "2026-10-16",
     "Weekly contractor review; temporary space secured as a two-week buffer.",
     "ss13"),
    ("D-03", RaidType.DEPENDENCY, "Master data cleansing cut-off gates migration validation",
     "Migration validation cannot begin until the cleansed vendor and customer masters "
     "are frozen on 2026-10-09.",
     Severity.HIGH, "Anneke de Vries", "2026-07-06", "2026-10-09",
     "Cut-off protected by the additional steward request; partial-freeze option assessed as fallback.",
     "ss24"),
    ("D-04", RaidType.DEPENDENCY, "Information Security review of the automation platform",
     "Wave 2 automation build depends on the platform-level security review, "
     "which is scheduled behind two higher-priority Group IT reviews.",
     Severity.MEDIUM, "Sofia Marchetti", "2026-08-10", "2026-09-30",
     "Review slot confirmed for 2026-09-22; evidence pack submitted early.",
     "ss32"),
    ("A-01", RaidType.ASSUMPTION, "Regional finance teams available for UAT",
     "Assumes regional finance teams provide 240 person-days for user acceptance testing "
     "in the October to December window, alongside the year-end close.",
     Severity.HIGH, "Daniel Okonkwo", "2026-05-18", "2026-09-25",
     "UAT scheduled around the close calendar; commitment to be confirmed at the September steering committee.",
     "ss23"),
    ("A-02", RaidType.ASSUMPTION, "Desk ratio of 1.4 holds for both hubs",
     "The footprint business case assumes a 1.4 desk ratio. A lower ratio would "
     "require additional Krakow floor space at a cost of EUR 0.6m.",
     Severity.MEDIUM, "Priya Raghunathan", "2026-05-25", "2026-11-20",
     "Ratio validated against the hybrid working policy; reviewed again at wave 2 planning.",
     "ss13"),
    ("A-03", RaidType.ASSUMPTION, "No statutory reporting changes land in scope during build",
     "Assumes no new statutory reporting requirement enters scope before Gate 4. "
     "One EU proposal is under consultation with a possible 2027 effective date.",
     Severity.LOW, "Marcus Adeyemi", "2026-04-20", "2026-11-20",
     "Group Finance Policy monitors the consultation and reports monthly to the programme board.",
     "ss21"),
    ("A-04", RaidType.ASSUMPTION, "Benefit baseline holds at the FY26 cost base",
     "Benefit measurement assumes the FY26 cost base as the baseline. "
     "A mid-year reorganisation in two regions could move the baseline.",
     Severity.MEDIUM, "Jonas Brenner", "2026-06-08", "2026-12-18",
     "Baseline frozen with Group Finance; any restatement to be handled as a change request.",
     "ss33"),
]

# id, name, date, sub-stream, major
MILESTONES = [
    ("m01", "Service catalogue v1 published", "2026-04-24", "ss11", False),
    ("m02", "Role architecture approved", "2026-05-08", "ss12", False),
    ("m03", "ERP template gap analysis closed", "2026-05-15", "ss31", False),
    ("m04", "Location assessment complete", "2026-05-22", "ss13", False),
    ("m05", "R2R and P2P designs signed off", "2026-05-29", "ss21", True),
    ("m06", "O2C design signed off", "2026-06-12", "ss23", False),
    ("m07", "Automation opportunity list approved", "2026-06-19", "ss32", False),
    ("m08", "Change impact assessment complete", "2026-06-26", "ss42", False),
    ("m09", "Master data model published", "2026-06-26", "ss24", False),
    ("m10", "Reporting design signed off", "2026-07-17", "ss33", False),
    ("m11", "Migration wave plan agreed", "2026-07-24", "ss41", False),
    ("m12", "SLAs agreed in all regions", "2026-07-31", "ss11", True),
    ("m13", "Krakow lease signed", "2026-08-07", "ss13", False),
    ("m14", "Wave 1 knowledge transfer starts", "2026-08-14", "ss41", True),
    ("m15", "ERP template build complete", "2026-09-11", "ss31", True),
    ("m16", "Control framework complete", "2026-09-11", "ss21", False),
    ("m17", "P2P build complete", "2026-09-25", "ss22", True),
    ("m18", "Wave 1 automations in production", "2026-10-02", "ss32", False),
    ("m19", "Master data cleansing cut-off", "2026-10-09", "ss24", True),
    ("m20", "Krakow fit-out handover", "2026-10-16", "ss13", False),
    ("m21", "Curriculum build complete", "2026-10-23", "ss42", False),
    ("m22", "Wave 1 stability review passed", "2026-10-30", "ss41", True),
    ("m23", "Integration test signed off", "2026-12-04", "ss31", True),
    ("m24", "UAT signed off", "2026-12-11", "ss22", False),
    ("m25", "Pilot close complete", "2026-11-27", "ss21", False),
    ("m26", "Wave 2 knowledge transfer complete", "2026-12-18", "ss41", False),
    ("m27", "Global cutover complete", "2027-01-08", "ss31", True),
    ("m28", "Wave 3 live", "2027-01-29", "ss41", True),
    ("m29", "Service review cycle 1 run to the new SLAs", "2026-11-13", "ss11", False),
    ("m30", "Consultation concluded in all regions", "2026-10-30", "ss12", False),
    ("m31", "Hub roles appointed", "2026-12-11", "ss12", True),
    ("m32", "O2C build complete", "2026-09-25", "ss23", False),
    ("m33", "Kuala Lumpur ramp complete", "2026-12-18", "ss13", False),
    ("m34", "Data layer live in test", "2026-11-06", "ss33", False),
    ("m35", "Performance dashboards live", "2027-01-22", "ss33", True),
    ("m36", "Migration validation complete", "2027-01-08", "ss24", False),
    ("m37", "Wave 1 training delivered", "2026-11-27", "ss42", False),
    ("m38", "Wave 2 automations live", "2027-01-15", "ss32", False),
]

# id, name, unit, baseline, current, target, direction, owner, sub-stream
#
# Benefits are judged against the delivery progress of the stream that produces
# them, not against elapsed calendar time - benefits back-load, so nothing
# realises until the build lands, and a calendar yardstick marks every measure
# late for the first two thirds of a programme.
#
# The current values are set so the picture is genuinely mixed: collections and
# the close are running ahead of their streams, change readiness well ahead,
# while touchless invoicing, master data and cost to serve lag the delivery that
# is supposed to be producing them. A benefits slide where every measure agrees
# with the plan is a benefits slide nobody believes.
BENEFITS = [
    ("b1", "Touchless invoice rate", "%", 41, 51, 75, BenefitDirection.UP,
     "Chiara Bellandi", "ss22"),
    ("b2", "Days sales outstanding", "days", 54, 49, 47, BenefitDirection.DOWN,
     "Daniel Okonkwo", "ss23"),
    ("b3", "Close cycle length", "days", 9, 7.5, 7, BenefitDirection.DOWN,
     "Marcus Adeyemi", "ss21"),
    ("b4", "Vendor master validation pass rate", "%", 77, 83, 98, BenefitDirection.UP,
     "Anneke de Vries", "ss24"),
    ("b5", "Automation benefit realised", "FTE", 0, 7.2, 18.0, BenefitDirection.UP,
     "Sofia Marchetti", "ss32"),
    ("b6", "Change readiness index", "index", 54, 71, 80, BenefitDirection.UP,
     "Laura Nkemelu", "ss42"),
    ("b7", "Finance cost to serve", "EUR m", 42.0, 39.9, 33.5, BenefitDirection.DOWN,
     "Jonas Brenner", "ss33"),
]

STEERING_COMMITTEE = [
    ("Helena Marchand", "Chief Financial Officer", "Northwind Group"),
    ("Arun Sethi", "Group Financial Controller", "Northwind Group"),
    ("Katrin Osei", "Chief Human Resources Officer", "Northwind Group"),
    ("Peer Wallenberg", "Chief Information Officer", "Northwind Group"),
    ("Maria Fontana", "Regional CFO, Europe", "Northwind Europe"),
    ("Sam Okada", "Regional CFO, Asia Pacific", "Northwind APAC"),
]

PROGRAMME_MANAGEMENT = [
    ("Nadia Bergström", "Programme Director", "Northwind GBS"),
    ("Felix Aumann", "Programme Manager", "Northwind GBS"),
    ("Grace Adeyinka", "PMO Lead", "Northwind GBS"),
    ("Tomasz Wieczorek", "Benefits & Reporting Lead", "Northwind GBS"),
    ("Ravi Balakrishnan", "Risk & Assurance Lead", "Northwind GBS"),
]

GOVERNANCE_COMMENTS = [
    "Steering committee meets monthly; two additional decision points are scheduled around Gate 3 and Gate 4.",
    "Programme board reviews RAID weekly and escalates any high-severity item open beyond 14 days.",
    "Work package leads hold delegated authority up to EUR 250k and one week of schedule float.",
    "Regional CFOs sign off wave readiness for their own entities; the CFO signs the global go / no-go.",
    "External Audit is consulted, not accountable, on the control framework and attends Gate 3 and Gate 5.",
]


def _build_work_packages(as_of: date) -> list[WorkPackage]:
    packages: list[WorkPackage] = []
    for spec in WORK_PACKAGES:
        sub_streams = []
        for ss in spec["sub_streams"]:
            phases = [
                Phase(
                    name=name,
                    start=_d(start),
                    end=_d(end),
                    status=_phase_status(_d(start), _d(end), as_of, at_risk),
                )
                for name, start, end, at_risk in ss["phases"]
            ]
            sub_streams.append(
                SubStream(
                    id=ss["id"],
                    name=ss["name"],
                    lead=ss["lead"],
                    objective=ss["objective"],
                    phases=phases,
                )
            )
        packages.append(
            WorkPackage(
                id=spec["id"],
                number=spec["number"],
                name=spec["name"],
                objective=spec["objective"],
                lead=spec["lead"],
                sub_streams=sub_streams,
                core_team=[Team(name=n, note=note) for n, note in spec["core_team"]],
                contributing_teams=[Team(name=n, note=note) for n, note in spec["contributing"]],
            )
        )
    return packages


def _next_milestone_id(sub_stream_id: str, after: date) -> str | None:
    upcoming = sorted(
        (m for m in MILESTONES if m[3] == sub_stream_id and _d(m[2]) >= after),
        key=lambda m: _d(m[2]),
    )
    return upcoming[0][0] if upcoming else None


def _build_weekly_status(as_of: date, history_weeks: int) -> list[WeeklyStatus]:
    """Current week is authored; earlier weeks are walked backwards from it."""
    statuses: list[WeeklyStatus] = []
    for spec in WORK_PACKAGES:
        for ss in spec["sub_streams"]:
            rag, progress, headline = ss["current"]
            pool: list[str] = ss["activities"]
            for back in range(history_weeks):
                day = as_of - timedelta(weeks=back)
                week = iso_week(day)
                # Progress decays going backwards; a stream moves 2-4 points a week.
                week_progress = max(5, progress - back * (3 if progress > 60 else 2))
                # Older weeks report from further down the pool, so the mix rotates.
                start = min(back, max(0, len(pool) - 3))
                activities = pool[start : start + 4] if len(pool) >= start + 4 else pool[-4:]
                if back == 0:
                    week_headline = headline
                    decisions = list(ss["decisions"])
                    week_rag = rag
                else:
                    # The week's lead activity is the honest headline for a past week.
                    lead = activities[0].rstrip(".")
                    week_headline = (
                        lead if rag is RAG.GREEN else f"{lead}; position remains under mitigation"
                    )
                    decisions = []
                    # Red streams were amber before they went red.
                    week_rag = RAG.AMBER if (rag is RAG.RED and back >= 2) else rag
                statuses.append(
                    WeeklyStatus(
                        week=week,
                        sub_stream_id=ss["id"],
                        rag=week_rag,
                        progress_pct=week_progress,
                        headline=week_headline,
                        activities=activities[:5],
                        decisions_needed=decisions,
                        next_milestone_id=_next_milestone_id(ss["id"], day),
                    )
                )
    return statuses


def _milestone_status(day: date, as_of: date, sub_stream_at_risk: bool) -> MilestoneStatus:
    if day < as_of:
        return MilestoneStatus.ACHIEVED
    if sub_stream_at_risk and day <= as_of + timedelta(days=60):
        return MilestoneStatus.AT_RISK
    return MilestoneStatus.ON_TRACK


def build_programme(as_of: date = AS_OF, history_weeks: int = HISTORY_WEEKS) -> Programme:
    """Assemble the full synthetic programme."""
    work_packages = _build_work_packages(as_of)

    at_risk_streams = {
        ss["id"]
        for spec in WORK_PACKAGES
        for ss in spec["sub_streams"]
        if ss["current"][0] in (RAG.AMBER, RAG.RED)
    }

    milestones = [
        Milestone(
            id=mid,
            name=name,
            date=_d(day),
            sub_stream_id=ss_id,
            status=_milestone_status(_d(day), as_of, ss_id in at_risk_streams),
            major=major,
        )
        for mid, name, day, ss_id, major in MILESTONES
    ]

    raid = [
        RaidItem(
            id=rid,
            type=rtype,
            title=title,
            description=desc,
            severity=sev,
            owner=owner,
            raised=_d(raised),
            due=_d(due),
            mitigation=mitigation,
            sub_stream_id=ss_id,
        )
        for rid, rtype, title, desc, sev, owner, raised, due, mitigation, ss_id in RAID
    ]

    gates = [
        StageGate(id=gid, number=num, name=name, date=_d(day), status=status, criteria=criteria)
        for gid, num, name, day, status, criteria in STAGE_GATES
    ]

    governance = Governance(
        steering_committee=[Person(name=n, role=r, org=o) for n, r, o in STEERING_COMMITTEE],
        steering_cadence="Monthly, third Thursday",
        programme_management=[Person(name=n, role=r, org=o) for n, r, o in PROGRAMME_MANAGEMENT],
        pmo_cadence="Weekly programme board, Tuesday",
        comments=GOVERNANCE_COMMENTS,
    )

    benefits = [
        BenefitMeasure(
            id=bid,
            name=name,
            unit=unit,
            baseline=baseline,
            current=current,
            target=target,
            direction=direction,
            owner=owner,
            sub_stream_id=ss_id,
            as_of=as_of,
        )
        for bid, name, unit, baseline, current, target, direction, owner, ss_id in BENEFITS
    ]

    return Programme(
        name="Project Meridian",
        client="Northwind GBS",
        subtitle="Global business services transformation",
        start=PROGRAMME_START,
        end=PROGRAMME_END,
        work_packages=work_packages,
        stage_gates=gates,
        raid=raid,
        milestones=milestones,
        weekly_status=_build_weekly_status(as_of, history_weeks),
        benefits=benefits,
        governance=governance,
    )


DEFAULT_PATH = Path(__file__).resolve().parent / "programme.json"


def main() -> None:
    programme = build_programme()
    out = programme.save(DEFAULT_PATH)
    print(
        f"Wrote {out} - {len(programme.work_packages)} work packages, "
        f"{len(programme.sub_streams)} sub-streams, {len(programme.raid)} RAID items, "
        f"{len(programme.milestones)} milestones, {len(programme.benefits)} benefit measures, "
        f"{len(programme.weekly_status)} weekly reports"
    )


if __name__ == "__main__":
    main()
