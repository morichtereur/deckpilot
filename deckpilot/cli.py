"""Consulting-grade PowerPoint status decks, generated from programme data.

\b
  deckpilot demo        generate the synthetic programme and build a deck
  deckpilot build       build from an existing programme file
  deckpilot render-one  render a single layout, for working on it
"""

from __future__ import annotations

import logging
import sys
from importlib import import_module
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


@cli.command(help="List the layouts this build can render.")
def layouts() -> None:
    """Descriptions come from each renderer's own docstring, so they cannot drift."""
    from deckpilot.renderer import deck as deck_module

    width = max(len(name) for name in deck_module.RENDERERS)
    missing = []
    for name in sorted(deck_module.RENDERERS):
        module = import_module(f"deckpilot.renderer.{name}")
        summary = (module.__doc__ or "").strip().splitlines()[0]
        if name not in SAMPLES:
            missing.append(name)
        click.echo(f"{'-' if name in missing else ' '} {name:<{width}}  {summary}")
    if missing:
        click.echo("\n- marks a layout with no sample spec, so render-one cannot show it.")


@cli.command(help="Run the geometry checks over a deck that already exists.")
@click.argument("deck_path", type=click.Path(exists=True, path_type=Path))
def check(deck_path: Path) -> None:
    findings = check_deck(deck_path)
    click.echo(report(findings))
    if any(f.severity == "error" for f in findings):
        raise SystemExit(1)


@cli.command(help="Convert a deck to PDF with LibreOffice.")
@click.argument("deck_path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=None,
              help="Output directory. Defaults to the deck's own directory.")
def pdf(deck_path: Path, out: Path | None) -> None:
    """Handy for circulating a read-only copy, and the first half of the visual QA
    loop that `scripts/qa.py` runs."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        from qa import to_pdf
    except ImportError as exc:  # pragma: no cover - only if scripts/ is missing
        raise click.ClickException(f"could not load the conversion helper: {exc}") from exc
    try:
        written = to_pdf(deck_path, out or deck_path.parent)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wrote {written}")


@cli.command("render-one", help="Render a single layout from its sample spec.")
@click.option("--layout", type=click.Choice(sorted(SAMPLES)), required=True)
@click.option("--out", type=click.Path(path_type=Path), default=Path("single.pptx"),
              show_default=True)
@click.option("--check/--no-check", default=True, show_default=True)
def render_one(layout: str, out: Path, check: bool) -> None:
    # A single layout carries no reporting week of its own; the sample specs are
    # built from the synthetic programme, so borrow its latest.
    spec = DeckSpec(
        title="deckpilot",
        subtitle=f"Single layout: {layout}",
        week=build_programme().weeks()[-1],
        slides=[SAMPLES[layout]],
    )
    deck.build_to(spec, out)
    _summarise(spec, out)
    if check:
        _run_checks(out)


if __name__ == "__main__":
    cli()
