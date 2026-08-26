"""LLM-assisted specification: the model edits the deck, it does not build it.

The division of labour is deliberate and narrow. The model chooses which RAID
items earn a place on a slide and how each action title is phrased. It does not
choose the layouts, the slide order, or anything about position, and it cannot
introduce a fact that is not already in the programme data - RAID items are
selected by id, never written as free text.

That is what makes the path safe to ship. The deterministic builder runs first
and produces a complete, valid deck; the model's output is then applied on top of
it. Anything that fails - a malformed response, a schema violation, an id that
does not exist, no API key at all - leaves the deterministic deck standing.
The LLM can improve the deck. It cannot break it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from deckpilot.data.models import Programme
from deckpilot.specgen import fallback
from deckpilot.specgen.schema import DeckSpec

log = logging.getLogger("deckpilot.specgen")

# The brief names this model; DECKPILOT_MODEL overrides it without a code change.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
ATTEMPTS = 2  # one call, then one retry carrying the validation error

SYSTEM_PROMPT = """\
You are a partner reviewing a transformation programme status deck before it goes \
to a steering committee. You are editing an existing deck, not writing one.

For each slide you are given, do two things.

1. Write the action title. An action title states the so-what, not the subject: \
"P2P build slips past Gate 3 without additional Group Tax capacity", not "P2P \
status update". Lead with the finding. Name the thing that is binding. Use the \
programme's own numbers. Do not exceed 150 characters, and never end with a full \
stop.

2. Choose which RAID items belong on the slide, by id, worst first. Pick at most \
four. Prefer items that a steering committee could actually act on this month \
over items that are merely open. Only use ids from the list you are given for \
that slide; leave the list empty to keep the current selection.

The subtitle is a quiet orienting line - what the slide covers and as at when. \
Keep it factual and under 120 characters.

Every number you use must come from the data you are given. Do not estimate, \
round, or infer figures that are not there.\
"""


class _Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SlideNarrative(_Narrative):
    slide_id: str = Field(description="The slide id exactly as given.")
    title: str = Field(min_length=1, max_length=155, description="The action title.")
    subtitle: str = Field(default="", max_length=160)
    raid_ids: list[str] = Field(
        default_factory=list, max_length=4,
        description="RAID ids for this slide, worst first. Empty keeps the current selection.",
    )


class DeckNarrative(_Narrative):
    slides: list[SlideNarrative] = Field(min_length=1, max_length=32)


def narrative_schema() -> dict[str, Any]:
    """The JSON schema sent to the API, with $refs inlined.

    Pydantic emits nested models as `$defs` plus `$ref`. Inlining keeps the schema
    a single self-contained object, which is what strict JSON-schema output wants.
    """
    schema = DeckNarrative.model_json_schema()
    defs = schema.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                return inline(defs[name])
            return {k: inline(v) for k, v in node.items()}
        if isinstance(node, list):
            return [inline(v) for v in node]
        return node

    return inline(schema)


# --------------------------------------------------------------------------
# The brief handed to the model
# --------------------------------------------------------------------------


def slide_id(index: int) -> str:
    return f"slide-{index + 1}"


def _scope_for(spec: DeckSpec, index: int, programme: Programme) -> set[str]:
    """Which sub-streams a slide covers, so its RAID choices stay on topic."""
    slide = spec.slides[index]
    if slide.layout == "workstream_charter":
        names = {c.name for c in slide.columns}
        return {ss.id for ss in programme.sub_streams if ss.name in names}
    if slide.layout in ("roadmap_gantt", "governance_chart"):
        return {ss.id for ss in programme.sub_streams}
    return set()


def build_brief(programme: Programme, week: str, spec: DeckSpec) -> dict[str, Any]:
    """Everything the model is allowed to know, and nothing it has to guess."""
    reports = {s.sub_stream_id: s for s in programme.status_for_week(week)}
    gates = [
        {"number": g.number, "name": g.name, "date": g.date.isoformat(), "status": g.status.value}
        for g in programme.stage_gates
    ]

    slides = []
    for i, slide in enumerate(spec.slides):
        if slide.layout == "section_divider":
            continue  # a divider carries no finding to state
        scope = _scope_for(spec, i, programme)
        slides.append(
            {
                "slide_id": slide_id(i),
                "layout": slide.layout,
                "current_title": slide.title,
                "current_subtitle": slide.subtitle or "",
                "sub_streams": [
                    {
                        "name": programme.sub_stream(ss_id).name,
                        "rag": reports[ss_id].rag.value,
                        "progress_pct": reports[ss_id].progress_pct,
                        "headline": reports[ss_id].headline,
                        "decisions_needed": list(reports[ss_id].decisions_needed),
                    }
                    for ss_id in sorted(scope)
                    if ss_id in reports
                ],
                "available_raid": [
                    {
                        "id": item.id,
                        "type": item.type.value,
                        "severity": item.severity.value,
                        "title": item.title,
                        "owner": item.owner,
                        "due": item.due.isoformat(),
                        "mitigation": item.mitigation,
                    }
                    for item in fallback.rank_raid(
                        [r for r in programme.raid if r.sub_stream_id in scope]
                    )
                ],
            }
        )

    return {
        "programme": programme.name,
        "client": programme.client,
        "reporting_week": week,
        "stage_gates": gates,
        "slides": slides,
    }


# --------------------------------------------------------------------------
# Applying the model's edits
# --------------------------------------------------------------------------


def _considerations(programme: Programme, ids: list[str], scope: set[str]) -> list[str] | None:
    """RAID lines for the ids the model chose, ignoring anything out of scope."""
    by_id = {item.id: item for item in programme.raid}
    chosen = [by_id[i] for i in ids if i in by_id and by_id[i].sub_stream_id in scope]
    return [fallback.raid_line(item) for item in chosen] if chosen else None


def apply_narrative(
    spec: DeckSpec, narrative: DeckNarrative, programme: Programme
) -> DeckSpec:
    """Overlay the model's titles and selections onto the deterministic deck.

    Anything the model did not speak to, or spoke to wrongly, keeps its
    deterministic value.
    """
    by_id = {s.slide_id: s for s in narrative.slides}
    slides = []
    for i, slide in enumerate(spec.slides):
        edit = by_id.get(slide_id(i))
        if edit is None or slide.layout == "section_divider":
            slides.append(slide)
            continue

        update: dict[str, Any] = {"title": edit.title.rstrip(". ")}
        if edit.subtitle.strip():
            update["subtitle"] = edit.subtitle.strip()
        chosen = _considerations(programme, edit.raid_ids, _scope_for(spec, i, programme))
        if chosen is not None:
            update["considerations"] = chosen
        slides.append(slide.model_copy(update=update))

    return spec.model_copy(update={"slides": slides})


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def _extract_text(response: Any) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("the response carried no text block")


def request_narrative(
    client: Any, brief: dict[str, Any], model: str = DEFAULT_MODEL, attempts: int = ATTEMPTS
) -> DeckNarrative | None:
    """Ask for a narrative, retrying once with the validation error in the prompt.

    Returns None when every attempt fails; the caller then keeps the
    deterministic deck.
    """
    schema = narrative_schema()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Here is the deck and the programme data behind it. Return an action "
                "title, a subtitle and a RAID selection for every slide listed.\n\n"
                + json.dumps(brief, indent=2)
            ),
        }
    ]

    response: Any = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
            return DeckNarrative.model_validate_json(_extract_text(response))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "specgen attempt %d/%d produced unusable output: %s", attempt, attempts, exc
            )
            if attempt == attempts:
                return None
            # Hand the model its own error. A second blind attempt is just a
            # second coin toss.
            messages += [
                {"role": "assistant", "content": _safe_text(response)},
                {
                    "role": "user",
                    "content": (
                        "That did not validate against the schema:\n\n"
                        f"{exc}\n\n"
                        "Return corrected JSON matching the schema exactly. "
                        "Change nothing else."
                    ),
                },
            ]
        except Exception as exc:  # noqa: BLE001 - transport, auth, rate limits
            log.warning("specgen call failed: %s", exc)
            return None
    return None


def _safe_text(response: Any) -> str:
    try:
        return _extract_text(response)
    except Exception:  # noqa: BLE001
        return "(unreadable response)"


def build_deck_spec_with_llm(
    programme: Programme,
    week: str | None = None,
    client: Any = None,
    model: str | None = None,
) -> DeckSpec:
    """Build the deterministic deck, then let the model edit it.

    Every failure path returns the deterministic deck, so this never produces a
    worse result than `--no-llm` - only a differently worded one.
    """
    baseline = fallback.build_deck_spec(programme, week)
    model = model or os.environ.get("DECKPILOT_MODEL", DEFAULT_MODEL)

    if client is None:
        try:
            import anthropic

            client = anthropic.Anthropic()
        except Exception as exc:  # noqa: BLE001 - missing package or credentials
            log.warning("no Anthropic client available (%s); keeping the deterministic deck", exc)
            return baseline

    brief = build_brief(programme, baseline.week, baseline)
    narrative = request_narrative(client, brief, model=model)
    if narrative is None:
        log.warning("the model returned nothing usable; keeping the deterministic deck")
        return baseline

    edited = apply_narrative(baseline, narrative, programme)
    try:
        # The overlay is validated in full before it is allowed to reach a renderer.
        return DeckSpec.model_validate(edited.model_dump(mode="json"))
    except ValidationError as exc:
        log.warning("the edited deck did not validate (%s); keeping the deterministic deck", exc)
        return baseline
