"""The LLM path's contract is that it can improve the deck but never break it.

Every test here is about what happens when the model misbehaves: malformed JSON,
a schema violation, an invented RAID id, a slide that does not exist, a title too
long, the API refusing to answer at all. In each case the deterministic deck has
to survive intact.

No test calls the API. CI has no key and should not need one.
"""

import json
import logging
from dataclasses import dataclass

import pytest

from deckpilot.data.generate import build_programme
from deckpilot.data.models import Programme
from deckpilot.specgen import fallback, llm
from deckpilot.specgen.schema import DeckSpec


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Response:
    content: list


class FakeClient:
    """Returns canned payloads in order, and records what it was asked."""

    def __init__(self, *payloads: str, raises: Exception | None = None):
        self.payloads = list(payloads)
        self.raises = raises
        self.calls: list[dict] = []

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        payload = self.payloads.pop(0) if self.payloads else "{}"
        return _Response(content=[_Block(text=payload)])


@pytest.fixture(scope="module")
def programme() -> Programme:
    return build_programme()


@pytest.fixture(scope="module")
def baseline(programme) -> DeckSpec:
    return fallback.build_deck_spec(programme)


def content_slide_ids(spec: DeckSpec) -> list[str]:
    return [
        llm.slide_id(i) for i, s in enumerate(spec.slides) if s.layout != "section_divider"
    ]


def good_payload(spec: DeckSpec, programme: Programme, raid_ids=None) -> str:
    slides = []
    for i, slide in enumerate(spec.slides):
        if slide.layout == "section_divider":
            continue
        ids = raid_ids if raid_ids is not None else []
        slides.append(
            {
                "slide_id": llm.slide_id(i),
                "title": f"Rewritten action title for {slide.layout}",
                "subtitle": "Rewritten subtitle",
                "raid_ids": ids,
            }
        )
    return json.dumps({"slides": slides})


# -- the brief ------------------------------------------------------------


def test_the_brief_omits_section_dividers(programme, baseline):
    brief = llm.build_brief(programme, baseline.week, baseline)
    assert brief["slides"]
    assert all(s["layout"] != "section_divider" for s in brief["slides"])


def test_the_brief_offers_only_in_scope_raid(programme, baseline):
    brief = llm.build_brief(programme, baseline.week, baseline)
    charter = next(s for s in brief["slides"] if s["layout"] == "workstream_charter")
    names = {ss["name"] for ss in charter["sub_streams"]}
    scope = {ss.id for ss in programme.sub_streams if ss.name in names}
    assert {r["id"] for r in charter["available_raid"]} == {
        r.id for r in programme.raid if r.sub_stream_id in scope
    }


def test_the_brief_carries_no_invented_numbers(programme, baseline):
    """Everything in the brief must be traceable to the programme data."""
    brief = llm.build_brief(programme, baseline.week, baseline)
    reported = {s.progress_pct for s in programme.status_for_week(baseline.week)}
    for slide in brief["slides"]:
        for ss in slide["sub_streams"]:
            assert ss["progress_pct"] in reported


def test_the_schema_is_self_contained():
    schema = llm.narrative_schema()
    assert "$defs" not in json.dumps(schema)
    assert schema["additionalProperties"] is False


# -- the happy path -------------------------------------------------------


def first_content_index(spec: DeckSpec) -> int:
    return next(i for i, s in enumerate(spec.slides) if s.layout != "section_divider")


def first_divider_index(spec: DeckSpec) -> int:
    return next(i for i, s in enumerate(spec.slides) if s.layout == "section_divider")


def test_a_valid_narrative_is_applied(programme, baseline):
    client = FakeClient(good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)

    assert len(client.calls) == 1
    divider = first_divider_index(baseline)
    assert spec.slides[divider] == baseline.slides[divider]  # dividers are untouched
    edited = [s for s in spec.slides if s.layout != "section_divider"]
    assert all(s.title.startswith("Rewritten action title") for s in edited)
    assert all(s.subtitle == "Rewritten subtitle" for s in edited)


def test_the_layouts_and_order_are_not_the_models_to_change(programme, baseline):
    client = FakeClient(good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert [s.layout for s in spec.slides] == [s.layout for s in baseline.slides]
    assert len(spec.slides) == len(baseline.slides)


def test_a_chosen_raid_selection_replaces_the_default(programme, baseline):
    charter_index = next(
        i for i, s in enumerate(baseline.slides) if s.layout == "workstream_charter"
    )
    scope = llm._scope_for(baseline, charter_index, programme)
    chosen = [r.id for r in programme.raid if r.sub_stream_id in scope][:2]
    assert chosen

    payload = json.loads(good_payload(baseline, programme))
    for slide in payload["slides"]:
        if slide["slide_id"] == llm.slide_id(charter_index):
            slide["raid_ids"] = chosen
    client = FakeClient(json.dumps(payload))

    spec = llm.build_deck_spec_with_llm(programme, client=client)
    considerations = spec.slides[charter_index].considerations
    assert len(considerations) == len(chosen)
    for item_id in chosen:
        item = next(r for r in programme.raid if r.id == item_id)
        assert any(c.startswith(item.title) for c in considerations)


def test_an_empty_selection_keeps_the_deterministic_one(programme, baseline):
    client = FakeClient(good_payload(baseline, programme, raid_ids=[]))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    for original, edited in zip(baseline.slides, spec.slides, strict=True):
        if original.layout == "section_divider":
            continue  # a divider has no considerations to keep
        assert edited.considerations == original.considerations


def test_a_trailing_full_stop_is_stripped_from_titles(programme, baseline):
    payload = json.loads(good_payload(baseline, programme))
    for slide in payload["slides"]:
        slide["title"] = "A title that ends badly."
    client = FakeClient(json.dumps(payload))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    for slide in spec.slides:
        assert not slide.title.endswith(".")


# -- misbehaviour ---------------------------------------------------------


def test_malformed_json_is_retried_once_then_falls_back(programme, baseline, caplog):
    client = FakeClient("{not json at all", "still {{{ not json")
    with caplog.at_level(logging.WARNING, logger="deckpilot.specgen"):
        spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert len(client.calls) == 2
    assert spec == baseline
    assert "unusable output" in caplog.text


def test_the_retry_carries_the_validation_error(programme, baseline):
    client = FakeClient("{not json", good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)

    assert len(client.calls) == 2
    retry_messages = client.calls[1]["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "did not validate" in retry_messages[-1]["content"]
    # And the corrected second attempt is the one that lands.
    assert spec.slides[first_content_index(spec)].title.startswith("Rewritten action title")


def test_a_schema_violation_is_retried(programme, baseline):
    index = first_content_index(baseline)
    too_long = json.dumps(
        {
            "slides": [
                {
                    "slide_id": llm.slide_id(index),
                    "title": "x" * 400,
                    "subtitle": "",
                    "raid_ids": [],
                }
            ]
        }
    )
    client = FakeClient(too_long, good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert len(client.calls) == 2
    assert spec.slides[index].title.startswith("Rewritten action title")


def test_an_unknown_slide_id_is_ignored(programme, baseline):
    payload = json.dumps(
        {"slides": [{"slide_id": "slide-999", "title": "Nowhere", "subtitle": "", "raid_ids": []}]}
    )
    client = FakeClient(payload)
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert spec == baseline


def test_an_invented_raid_id_is_dropped(programme, baseline):
    charter_index = next(
        i for i, s in enumerate(baseline.slides) if s.layout == "workstream_charter"
    )
    payload = json.loads(good_payload(baseline, programme))
    for slide in payload["slides"]:
        if slide["slide_id"] == llm.slide_id(charter_index):
            slide["raid_ids"] = ["R-99", "TOTALLY-MADE-UP"]
    client = FakeClient(json.dumps(payload))

    spec = llm.build_deck_spec_with_llm(programme, client=client)
    # Nothing valid was chosen, so the deterministic selection stands.
    assert spec.slides[charter_index].considerations == (
        baseline.slides[charter_index].considerations
    )


def test_an_out_of_scope_raid_id_is_dropped(programme, baseline):
    """A model cannot move another work package's risk onto this slide."""
    charter_index = next(
        i for i, s in enumerate(baseline.slides) if s.layout == "workstream_charter"
    )
    scope = llm._scope_for(baseline, charter_index, programme)
    outsider = next(r.id for r in programme.raid if r.sub_stream_id not in scope)

    payload = json.loads(good_payload(baseline, programme))
    for slide in payload["slides"]:
        if slide["slide_id"] == llm.slide_id(charter_index):
            slide["raid_ids"] = [outsider]
    client = FakeClient(json.dumps(payload))

    spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert spec.slides[charter_index].considerations == (
        baseline.slides[charter_index].considerations
    )


def test_a_response_with_no_text_block_falls_back(programme, baseline):
    class Empty(FakeClient):
        def create(self, **kwargs):
            self.calls.append(kwargs)
            return _Response(content=[])

    client = Empty()
    assert llm.build_deck_spec_with_llm(programme, client=client) == baseline


def test_a_transport_failure_falls_back_without_retrying(programme, baseline, caplog):
    client = FakeClient(raises=RuntimeError("connection reset"))
    with caplog.at_level(logging.WARNING, logger="deckpilot.specgen"):
        spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert len(client.calls) == 1  # transport errors are not worth a second coin toss
    assert spec == baseline
    assert "connection reset" in caplog.text


def test_no_credentials_means_the_deterministic_deck(programme, baseline, monkeypatch, caplog):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "anthropic.Anthropic", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no api key"))
    )
    with caplog.at_level(logging.WARNING, logger="deckpilot.specgen"):
        assert llm.build_deck_spec_with_llm(programme) == baseline
    assert "keeping the deterministic deck" in caplog.text


def test_the_edited_deck_always_validates(programme, baseline):
    client = FakeClient(good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    assert DeckSpec.model_validate(spec.model_dump(mode="json")) == spec


def test_the_edited_deck_still_renders(programme, baseline):
    from deckpilot.renderer import deck
    from deckpilot.renderer.qa import check_slide

    client = FakeClient(good_payload(baseline, programme))
    spec = llm.build_deck_spec_with_llm(programme, client=client)
    prs = deck.build(spec)
    for i, slide in enumerate(prs.slides, start=1):
        assert [f for f in check_slide(i, slide) if f.severity == "error"] == []


# -- configuration --------------------------------------------------------


def test_the_model_defaults_to_the_briefed_one(programme, baseline, monkeypatch):
    monkeypatch.delenv("DECKPILOT_MODEL", raising=False)
    client = FakeClient(good_payload(baseline, programme))
    llm.build_deck_spec_with_llm(programme, client=client)
    assert client.calls[0]["model"] == llm.DEFAULT_MODEL == "claude-sonnet-4-6"


def test_the_model_can_be_overridden_by_environment(programme, baseline, monkeypatch):
    monkeypatch.setenv("DECKPILOT_MODEL", "claude-opus-5")
    client = FakeClient(good_payload(baseline, programme))
    llm.build_deck_spec_with_llm(programme, client=client)
    assert client.calls[0]["model"] == "claude-opus-5"


def test_the_request_asks_for_schema_constrained_output(programme, baseline):
    client = FakeClient(good_payload(baseline, programme))
    llm.build_deck_spec_with_llm(programme, client=client)
    config = client.calls[0]["output_config"]
    assert config["format"]["type"] == "json_schema"
    assert config["format"]["schema"] == llm.narrative_schema()
