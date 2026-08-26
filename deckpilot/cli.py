"""Consulting-grade PowerPoint status decks, generated from programme data.

\b
  deckpilot demo        generate the synthetic programme and build a deck
  deckpilot build       build from an existing programme file
  deckpilot render-one  render a single layout, for working on it
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from deckpilot.data.generate import DEFAULT_PATH, build_programme
from deckpilot.data.models import Programme
from deckpilot.renderer import deck
from deckpilot.renderer.qa import check_deck, report
from deckpilot.specgen.fallback import build_deck_spec
from deckpilot.specgen.samples import SAMPLES
from deckpilot.specgen.schema import DeckSpec

log = logging.getLogger("deckpilot")


class _Formatter(logging.Formatter):
    """Overflow warnings are the ones worth seeing, so they are not buried."""

    def format(self, record: logging.LogRecord) -> str:
        prefix = {"WARNING": "warning: ", "ERROR": "error: "}.get(record.levelname, "")
        return f"{prefix}{record.getMessage()}"


def _configure_logging(verbose: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_Formatter())
    root = logging.getLogger("deckpilot")
    root.handlers = [handler]
    root.setLevel(logging.INFO if verbose else logging.WARNING)


def _summarise(spec: DeckSpec, path: Path) -> None:
    counts: dict[str, int] = {}
    for slide in spec.slides:
        counts[slide.layout] = counts.get(slide.layout, 0) + 1
    breakdown = ", ".join(f"{n} x {layout}" for layout, n in sorted(counts.items()))
    click.echo(f"Wrote {path} - {len(spec.slides)} slides ({breakdown})")


def _run_checks(path: Path) -> None:
    findings = check_deck(path)
    click.echo(report(findings))


@click.group(help=__doc__)
@click.version_option(package_name="deckpilot")
@click.option("-v", "--verbose", is_flag=True, help="Show progress as well as warnings.")
def cli(verbose: bool) -> None:
    _configure_logging(verbose)


@cli.command(help="Generate the synthetic programme and build a deck from it, end to end.")
@click.option("--out", type=click.Path(path_type=Path), default=Path("examples/deck.pptx"),
              show_default=True)
@click.option("--week", default=None, help="ISO week to report, e.g. 2026-W35. Defaults to latest.")
@click.option("--check/--no-check", default=True, show_default=True,
              help="Run the geometry checks after building.")
def demo(out: Path, week: str | None, check: bool) -> None:
    programme = build_programme()
    programme.save(DEFAULT_PATH)
    click.echo(f"Wrote {DEFAULT_PATH} - {len(programme.sub_streams)} sub-streams, "
               f"{len(programme.raid)} RAID items")
    spec = build_deck_spec(programme, week)
    deck.build_to(spec, out)
    _summarise(spec, out)
    if check:
        _run_checks(out)


@cli.command(help="Build a deck from an existing programme file.")
@click.option("--data", type=click.Path(exists=True, path_type=Path), default=DEFAULT_PATH,
              show_default=True)
@click.option("--week", default=None, help="ISO week to report, e.g. 2026-W35. Defaults to latest.")
@click.option("--out", type=click.Path(path_type=Path), default=Path("deck.pptx"),
              show_default=True)
@click.option("--llm", is_flag=True, help="Let the model select content and write the titles.")
@click.option("--spec-out", type=click.Path(path_type=Path), default=None,
              help="Also write the slide specification as JSON.")
@click.option("--check/--no-check", default=True, show_default=True)
def build(data: Path, week: str | None, out: Path, llm: bool, spec_out: Path | None,
          check: bool) -> None:
    programme = Programme.load(data)
    if llm:
        from deckpilot.specgen.llm import build_deck_spec_with_llm

        spec = build_deck_spec_with_llm(programme, week)
    else:
        spec = build_deck_spec(programme, week)
    if spec_out:
        spec.save(spec_out)
        click.echo(f"Wrote {spec_out}")
    deck.build_to(spec, out)
    _summarise(spec, out)
    if check:
        _run_checks(out)


@cli.command("render-one", help="Render a single layout from its sample spec.")
@click.option("--layout", type=click.Choice(sorted(SAMPLES)), required=True)
@click.option("--out", type=click.Path(path_type=Path), default=Path("single.pptx"),
              show_default=True)
@click.option("--check/--no-check", default=True, show_default=True)
def render_one(layout: str, out: Path, check: bool) -> None:
    spec = DeckSpec(
        title="deckpilot",
        subtitle=f"Single layout: {layout}",
        week="0000-W00",
        slides=[SAMPLES[layout]],
    )
    deck.build_to(spec, out)
    _summarise(spec, out)
    if check:
        _run_checks(out)


if __name__ == "__main__":
    cli()
