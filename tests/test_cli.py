"""End-to-end: the commands a reader of the README will actually run."""

import logging

import pytest
from click.testing import CliRunner
from pptx import Presentation

from deckpilot.cli import cli
from deckpilot.data.generate import build_programme
from deckpilot.renderer.qa import check_deck
from deckpilot.specgen.samples import SAMPLES


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_demo_builds_a_deck_without_an_api_key(runner, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "deck.pptx"
    result = runner.invoke(cli, ["demo", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()

    prs = Presentation(str(out))
    assert len(prs.slides) >= 8
    assert "Geometry check: clean." in result.output


def test_the_demo_deck_has_no_overflow_warnings(runner, tmp_path, caplog):
    out = tmp_path / "deck.pptx"
    with caplog.at_level(logging.WARNING, logger="deckpilot.renderer"):
        result = runner.invoke(cli, ["demo", "--out", str(out)])
    assert result.exit_code == 0
    assert "truncated" not in caplog.text, caplog.text


def test_the_demo_deck_is_geometrically_clean(runner, tmp_path):
    out = tmp_path / "deck.pptx"
    assert runner.invoke(cli, ["demo", "--out", str(out)]).exit_code == 0
    assert [f for f in check_deck(out) if f.severity == "error"] == []


def test_build_reads_a_programme_file(runner, tmp_path):
    data = tmp_path / "programme.json"
    build_programme().save(data)
    out = tmp_path / "deck.pptx"
    spec_out = tmp_path / "spec.json"
    result = runner.invoke(
        cli,
        ["build", "--data", str(data), "--week", "2026-W34", "--out", str(out),
         "--spec-out", str(spec_out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists() and spec_out.exists()


def test_build_refuses_a_week_it_has_no_data_for(runner, tmp_path):
    data = tmp_path / "programme.json"
    build_programme().save(data)
    result = runner.invoke(
        cli, ["build", "--data", str(data), "--week", "1999-W01",
              "--out", str(tmp_path / "d.pptx")]
    )
    assert result.exit_code != 0
    assert "no status reported" in str(result.exception)


@pytest.mark.parametrize("layout", sorted(SAMPLES))
def test_render_one_renders_each_layout_alone(runner, tmp_path, layout):
    out = tmp_path / f"{layout}.pptx"
    result = runner.invoke(cli, ["render-one", "--layout", layout, "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert len(Presentation(str(out)).slides) == 1
    assert "Geometry check: clean." in result.output


def test_render_one_rejects_an_unknown_layout(runner, tmp_path):
    result = runner.invoke(cli, ["render-one", "--layout", "nope", "--out", str(tmp_path / "x")])
    assert result.exit_code != 0


def test_every_layout_has_a_sample_and_a_renderer():
    from deckpilot.renderer.deck import RENDERERS

    assert set(SAMPLES) <= set(RENDERERS)
