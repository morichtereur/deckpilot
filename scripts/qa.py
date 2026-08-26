#!/usr/bin/env python
"""Build-inspect loop: lint a deck's geometry, then render every slide to PNG.

    python scripts/qa.py out/deck.pptx [--images-only] [--no-images] [--dpi 150]

Two passes, because they catch different faults. The geometry linter finds what
eyes are bad at - a shape three thousandths of an inch over the margin, two boxes
overlapping by 4% - and it needs no rendering at all. The images find what only
eyes catch: crowding, an awkward wrap, a colour that fights the page.

Rendering is headless, in two steps. LibreOffice converts the .pptx to PDF, and
macOS's own PDF rasteriser turns each page into a PNG. An earlier version drove
Keynote over AppleScript; it worked until the machine's GUI layer wedged and took
the QA loop down with it, which is a bad property for the one tool that is
supposed to tell you whether the build is sound.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deckpilot.renderer.qa import check_deck, report  # noqa: E402

SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
DEFAULT_DPI = 150


def _soffice() -> Path:
    if SOFFICE.exists():
        return SOFFICE
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return Path(found)
    raise RuntimeError(
        "LibreOffice not found. Install it from https://www.libreoffice.org/download/ "
        "or pass --no-images to run the geometry check alone."
    )


def to_pdf(pptx: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(_soffice()), "--headless", "--norestore",
            "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx),
        ],
        capture_output=True, text=True, timeout=900, check=False,
    )
    pdf = out_dir / f"{pptx.stem}.pdf"
    if result.returncode != 0 or not pdf.exists():
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"PDF conversion failed: {detail}")
    return pdf


def rasterise(pdf: Path, out_dir: Path, dpi: int = DEFAULT_DPI) -> list[Path]:
    """One PNG per page, via CoreGraphics. No GUI application involved."""
    try:
        import Quartz
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "pyobjc-framework-Quartz is needed to rasterise slides: pip install -e '.[qa]'"
        ) from exc

    url = Quartz.CFURLCreateWithFileSystemPath(
        None, str(pdf), Quartz.kCFURLPOSIXPathStyle, False
    )
    doc = Quartz.CGPDFDocumentCreateWithURL(url)
    if doc is None:
        raise RuntimeError(f"could not open {pdf}")

    out_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    written: list[Path] = []

    for number in range(1, Quartz.CGPDFDocumentGetNumberOfPages(doc) + 1):
        page = Quartz.CGPDFDocumentGetPage(doc, number)
        box = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
        width = int(round(box.size.width * scale))
        height = int(round(box.size.height * scale))

        space = Quartz.CGColorSpaceCreateDeviceRGB()
        ctx = Quartz.CGBitmapContextCreate(
            None, width, height, 8, 0, space,
            Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Host,
        )
        # PDF pages are transparent where nothing is drawn; slides are not.
        Quartz.CGContextSetRGBFillColor(ctx, 1.0, 1.0, 1.0, 1.0)
        Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, width, height))
        Quartz.CGContextScaleCTM(ctx, scale, scale)
        Quartz.CGContextDrawPDFPage(ctx, page)

        image = Quartz.CGBitmapContextCreateImage(ctx)
        target = out_dir / f"slide-{number:02d}.png"
        dest_url = Quartz.CFURLCreateWithFileSystemPath(
            None, str(target), Quartz.kCFURLPOSIXPathStyle, False
        )
        dest = Quartz.CGImageDestinationCreateWithURL(dest_url, "public.png", 1, None)
        Quartz.CGImageDestinationAddImage(dest, image, None)
        if not Quartz.CGImageDestinationFinalize(dest):
            raise RuntimeError(f"could not write {target}")
        written.append(target)

    return written


def export_images(pptx: Path, out_dir: Path, dpi: int = DEFAULT_DPI) -> list[Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    pdf = to_pdf(pptx, out_dir)
    return rasterise(pdf, out_dir, dpi)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pptx", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="image output directory")
    ap.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--images-only", action="store_true")
    args = ap.parse_args()

    findings = []
    if not args.images_only:
        findings = check_deck(args.pptx)
        print(report(findings))

    if not args.no_images:
        out = args.out or args.pptx.parent / f"{args.pptx.stem}_png"
        images = export_images(args.pptx, out, args.dpi)
        print(f"Rendered {len(images)} slide image(s) to {out}")

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
