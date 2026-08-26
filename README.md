# deckpilot

[![CI](https://github.com/morichtereur/deckpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/morichtereur/deckpilot/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/licence-MIT-green.svg)](LICENSE)

**Consulting-grade PowerPoint status decks, generated from structured programme data.**

Feed it a transformation programme — work packages, stage gates, a RAID log, a benefit
case, a budget, weekly sub-stream reports — and it produces a twenty-one-slide deck that
a consultant could take into a steering committee without apologising for it. Every slide
is built from native PowerPoint shapes: the text is selectable, the roadmap bars are
draggable, the RAID log is a real table you can sort. Nothing is an image. Every content
slide carries speaker notes derived from the same figures. It runs end to end with no
API key.

![Executive summary](examples/screenshots/exec-summary.png)

---

## Quickstart

```bash
git clone https://github.com/morichtereur/deckpilot.git
cd deckpilot
python -m venv .venv && source .venv/bin/activate
pip install -e .
deckpilot demo
```

That writes `examples/deck.pptx` and runs the geometry checks over it. No API key,
no network, no configuration.

```
Wrote deckpilot/data/programme.json - 12 sub-streams, 18 RAID items
Wrote examples/deck.pptx - 21 slides (1 x agenda, 1 x benefits_bridge,
  1 x criteria_columns, 1 x exec_summary, 1 x financial_summary,
  1 x governance_chart, 1 x kpi_scorecard, 3 x raid_table, 1 x roadmap_gantt,
  6 x section_divider, 1 x status_overview, 3 x workstream_charter)
Geometry check: clean.
```

Other commands:

```bash
deckpilot build --data deckpilot/data/programme.json --week 2026-W34 --out deck.pptx
deckpilot build --data deckpilot/data/programme.json --out deck.pptx --llm
deckpilot render-one --layout roadmap_gantt --out single.pptx
deckpilot layouts
deckpilot check deck.pptx
deckpilot pdf deck.pptx
```

`render-one` builds a single layout from its sample spec, which is how you work on one
without rebuilding twenty other slides first. `check` runs the geometry linter over a
deck that already exists, and `layouts` lists what this build can render.

---

## How it works

```mermaid
flowchart LR
    A["Programme data<br/><i>pydantic, self-validating</i>"] --> B["Spec generation"]
    B --> C["SlideSpec<br/><i>what goes on a slide</i>"]
    C --> D["Renderer<br/><i>where it goes</i>"]
    D --> E["deck.pptx<br/><i>native shapes</i>"]

    B --> B1["Deterministic builder<br/><i>always runs</i>"]
    B --> B2["LLM overlay<br/><i>optional, --llm</i>"]
    B1 --> C
    B2 -.->|"on any failure"| B1

    E --> F["Geometry linter"]
    E --> G["LibreOffice → PDF → PNG"]
```

The pipeline has one load-bearing split: **content decisions and layout decisions never
mix.** A `SlideSpec` says which RAID items appear on a slide and how the action title is
phrased. It says nothing about position, size or colour — those come from
`deckpilot/theme/tokens.py` and are computed by the layout. That is what makes it safe to
let a language model touch the deck at all.

| Module | Responsibility |
|---|---|
| `data/` | The programme model and a hand-authored synthetic dataset |
| `renderer/timeline.py` | Roadmap date arithmetic, isolated so it can be tested as arithmetic |
| `theme/tokens.py` | Every colour, size and grid constant in the project |
| `specgen/` | Deterministic spec builder, plus the optional LLM overlay |
| `renderer/` | One module per layout, over a shared fitting and shape toolkit |
| `renderer/qa.py` | Geometry linter — off-slide, over-margin, colliding, crowded |

---

## Layouts

| | |
|---|---|
| **Workstream charter** — N sub-stream columns crossed by two labelled bands, so a reader can compare one row across every column | ![](examples/screenshots/workstream-charter.png) |
| **Roadmap** — month grid, bars coloured by schedule state, milestone diamonds, a reporting-date line, and parallel phases stacked into lanes | ![](examples/screenshots/roadmap-gantt.png) |
| **Status overview** — one card per work package: rating, progress bar, what is happening, what is next | ![](examples/screenshots/status-overview.png) |
| **RAID table** — a real PowerPoint table, grouped by type, severity carried by the cell fill | ![](examples/screenshots/raid-table.png) |
| **Governance chart** — three tiers joined by native connectors, each work package split into core and contributing teams | ![](examples/screenshots/governance-chart.png) |
| **Criteria columns** — a question per column and the characteristics that answer it; also covers WHY / WHAT / HOW framings | ![](examples/screenshots/criteria-columns.png) |
| **Executive summary** — rated verdict, the messages behind it, the decisions being asked for | ![](examples/screenshots/exec-summary.png) |
| **Benefits bridge** — the cost case as a waterfall, baseline to target, one column per lever, with a truncated axis the slide admits to | ![](examples/screenshots/benefits-bridge.png) |
| **Financial summary** — budget against forecast at completion, variance as a diverging bar, and contingency drawn against time elapsed | ![](examples/screenshots/financial-summary.png) |
| **KPI scorecard** — benefit measures from baseline to target, each bar marked at the delivery progress of the stream producing it | ![](examples/screenshots/kpi-scorecard.png) |
| **Agenda** — sections and the page each one starts on, resolved after the appendix has been paginated | ![](examples/screenshots/agenda.png) |
| **RAID appendix** — the full log split across as many slides as it needs, with split groups re-announced | ![](examples/screenshots/raid-appendix.png) |
| **Section divider** — a full-bleed break, and the only slide in the deck with no footer | ![](examples/screenshots/section-divider.png) |

---

## Why this is hard

The interesting problem here is not the language model. It is one API call. The
difficulty is that PowerPoint is a fixed canvas and text is not fixed-size, and the
library that writes the file cannot see either.

**python-pptx never renders.** It writes XML. So nothing in the library can tell you
whether a string fits its box. PowerPoint's own autofit is not a way out either: it runs
at open time on the reader's machine, which means the `.pptx` on disk would contain sizes
nobody chose, and two people opening the same file could see different decks. So
`renderer/text_metrics.py` carries Calibri's advance widths and does the wrapping itself.
Every size decision is made at build time and written into the file explicitly.

**Fitting each box on its own produces a slide that looks broken.** One column's header
lands a point smaller than its neighbour's, nothing overflows, and the slide still reads
as a mistake. Peers have to be fitted as a group, at one shared size set by the tightest
member.

**Whitespace has to go somewhere deliberate.** A bulleted list that stops a third of the
way up its box looks like a box that was sized wrong. Leftover height is pushed into the
gaps between bullets, shared across a band so peer columns stay on the same baselines —
and where a block genuinely has less to say than the slide has room, the block is sized
to its content and the page simply ends early. A half-empty box is worse than white space.

**The edges are where roadmaps break.** A bar starting before the window, a bar ending
after it, a one-day task that rounds away to nothing, a milestone on the last day of the
last month, two migration waves that genuinely overlap and must not be drawn on top of
each other. That arithmetic lives in `renderer/timeline.py` on its own precisely so it
can be tested as arithmetic instead of by squinting at a slide.

**A table row height is a minimum, not a maximum.** Set one on a python-pptx table and
PowerPoint will still grow the row if a cell wraps further — and the table walks off the
bottom of the slide. Row heights have to be computed from the wrapped line count.

**Pagination is a measurement problem, and the trade runs both ways.** Type size and page
count trade against each other. For a summary slide the count is fixed at one and the type
has to give; for an appendix a slide costs nothing and unreadable type costs the reader, so
it holds the dense size and adds slides instead. Filling greedily then leaves sixteen rows
on one slide and two on the next, so the per-slide budget is shrunk as far as it will go
without adding a slide — which spreads the same rows evenly, nine and nine. And because the
paginator's size is also the renderer's ceiling, every page comes out at the same size: a
second slide set a point off the first looks like a different document.

**Defaults leak.** python-pptx attaches a theme style block to every new autoshape, which
carries a drop shadow. An empty `<a:effectLst/>` suppresses it in PowerPoint but not in
every renderer, so the whole style block is stripped — a deck whose shapes grow shadows
depending on who opens it is not a deck you control.

**An exhibit can be accurate and still dishonest.** A cost bridge drawn from zero turns
every lever into a sliver, so the axis is truncated — and the slide says so, because a
truncated axis nobody declared is a chart that misleads on purpose. A step too small to
see is still drawn at a minimum height: dropping it would leave an unexplained gap in the
bridge, and the label states the real number either way. The model refuses a case that
does not reconcile, so a bridge whose levers do not add up to its target will not load.

**A number needs something to be measured against.** A benefit 29% of the way to target is
good or bad depending on how much of the work that produces it has been done, so each bar
on the scorecard carries a marker at the delivery progress of its own sub-stream. Measuring
benefits against elapsed calendar time — the obvious first choice — marks every measure late
for the first two thirds of a programme, because benefits back-load.

Then there is the part that only shows up on a screen: white bar labels are unreadable on
the pale "complete" fill and fine on the deep "in progress" one, so label colour is chosen
per fill by WCAG contrast ratio. Every combination in the deck clears 4.1:1.

---

## The LLM path

`--llm` is an overlay, not a generator. The deterministic builder runs first and produces
a complete, valid deck. The model is then asked to do two things: write the action titles,
and choose which RAID items earn a place on each slide.

It chooses RAID items **by id**, never as free text, so it cannot introduce a fact that is
not already in the programme data — and an id belonging to another work package is dropped
rather than moved onto the slide. It does not choose layouts, slide order, or anything
about position.

Every failure path returns the deterministic deck: malformed JSON, a schema violation, an
invented id, a slide that does not exist, a transport error, no API key at all. A failed
response is retried once with its own validation error attached, because a second blind
attempt is just a second coin toss. **The model can improve the deck. It cannot break it.**

No test calls the API, and CI does not need a key.

---

## Quality checks

Two passes, because they catch different faults.

```bash
python scripts/qa.py examples/deck.pptx        # lint the geometry, then render every slide
deckpilot check examples/deck.pptx             # the geometry half, on its own
pytest                                          # 316 tests
ruff check .
```

The **geometry linter** finds what eyes are bad at — a shape three thousandths of an inch
over the margin, two boxes overlapping by four percent, neighbours that nearly touch. It
needs no rendering, so it runs inside the test suite and after every build. Shapes are
named, so it can tell a title and subtitle set deliberately tight from two boxes that
collided (`bleed:` crosses the margin on purpose, `marker:` sits on top of something on
purpose, `surface:` is a background band other content comes right up to).

The **visual pass** finds what only eyes catch — including one class of fault the linter
cannot see at all. A table's *declared* height can be perfectly within the content area
while the *rendered* table runs into the footer, because a row height is a floor and the
renderer grows anything under-declared. A cell's line box in a table turned out to be about
1.48x the font size against the 1.22x an ordinary text frame uses; nothing but a rendered
page shows that.

The visual pass `scripts/qa.py` converts the deck to PDF
with LibreOffice and rasterises each page with CoreGraphics — headless, about four seconds
for a deck, with no GUI application involved. It needs LibreOffice on the path and, on
macOS, `pip install -e '.[qa]'` for the rasteriser.

A shipped deck should produce no `WARNING`s. When text genuinely will not fit its box even
at the minimum size, `fit_text` truncates with an ellipsis and logs the slide and element
by name — that is a content or layout decision to make, not something to hide by clipping.

---

## Development

```bash
pip install -e '.[dev,qa]'
pytest
ruff check .
python -m deckpilot.data.generate     # regenerate the synthetic programme
```

Speaker notes are generated alongside each slide from the same figures, in the spec builder
rather than in the renderer, so a note cannot quote a number the slide does not show. That
is the usual failure of speaker notes — written once, then left behind by the data.

The dataset in `data/generate.py` is hand-authored rather than randomised. A status deck
only reads as real if the RAID log argues with the roadmap and the weekly reports argue
with both, and random generators do not produce that. Only history is derived: each
sub-stream states its current week honestly, and earlier weeks are walked backwards from it.

Everything in it is fictional — "Northwind GBS" is not a company, and none of the people,
teams or numbers are real.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'deckpilot'` right after `pip install -e .`**
— on macOS, check whether the install's path file has picked up the hidden flag:

```bash
ls -lO .venv/lib/python3.*/site-packages/*.pth
```

`site` silently skips a `.pth` file marked `hidden`, so the editable install is never
put on the path and nothing reports an error. Clear it:

```bash
chflags nohidden .venv/lib/python3.*/site-packages/*.pth
```

If the flag keeps coming back, something on the machine is re-applying it — run the CLI as
`python -m deckpilot.cli ...` instead, which does not depend on the path file.

**`scripts/qa.py` cannot find LibreOffice** — it looks in `/Applications/LibreOffice.app`
and then on `PATH`. Pass `--no-images` to run the geometry check alone; that half needs
nothing but Python.

---

## Licence

MIT. See [LICENSE](LICENSE).
