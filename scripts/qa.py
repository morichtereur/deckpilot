#!/usr/bin/env python
"""Build-inspect loop: lint a deck's geometry, then render every slide to PNG.

The brief's tooling (`soffice` + `pdftoppm`) is not available on this machine,
so slide images come from Keynote, which opens the same .pptx and renders every
slide. Fidelity is close enough for layout review; PowerPoint remains the
reference for anything typographic.

    python scripts/qa.py out/deck.pptx [--images-only] [--no-images]
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deckpilot.renderer.qa import check_deck, report  # noqa: E402

# Address Keynote by bundle id, not by name. Third-party apps ship with "Keynote"
# in their name, and once Apple's Keynote is not already running, AppleScript will
# happily resolve the name to one of them and then sit there not responding.
KEYNOTE = "com.apple.iWork.Keynote"

# Keynote's default AppleEvent timeout is about two minutes, which a large deck
# can exceed while it lays out slides. Ask for longer rather than guessing.
EXPORT_SCRIPT = """
set inF to POSIX file "{src}"
set outF to POSIX file "{dst}"
with timeout of 900 seconds
	tell application id "{app}"
		set theDoc to open inF
		delay 1
		set opts to {{image format:PNG, skipped slides:false}}
		export theDoc to outF as slide images with properties opts
		close theDoc saving no
	end tell
end timeout
"""


def _quit_keynote() -> None:
    """Start from a clean slate.

    A previous run that timed out can leave a document open, and Keynote will
    then sit on a modal dialog instead of opening the next one - which looks
    like a hang rather than an error.
    """
    with contextlib.suppress(subprocess.TimeoutExpired):
        subprocess.run(
            ["osascript", "-e", f'tell application id "{KEYNOTE}" to quit saving no'],
            capture_output=True, text=True, timeout=30, check=False,
        )
    subprocess.run(["killall", "-9", "Keynote"], capture_output=True, check=False)


def export_images(pptx: Path, out_dir: Path) -> list[Path]:
    _quit_keynote()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    script = EXPORT_SCRIPT.format(src=pptx.resolve(), dst=out_dir.resolve(), app=KEYNOTE)
    result = subprocess.run(
        ["osascript", "-"], input=script, capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0 or "error" in result.stderr.lower():
        raise RuntimeError(f"Keynote export failed: {result.stderr.strip()}")
    return sorted(out_dir.rglob("*.png"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="image output directory")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--images-only", action="store_true")
    args = ap.parse_args()

    findings = []
    if not args.images_only:
        findings = check_deck(args.pptx)
        print(report(findings))

    if not args.no_images:
        out = args.out or args.pptx.parent / f"{args.pptx.stem}_png"
        images = export_images(args.pptx, out)
        print(f"Rendered {len(images)} slide image(s) to {out}")

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
