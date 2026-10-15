"""Render assets/rockforge*.svg into assets/rockforge.ico (and the 256 px PNG).

The .ico carries one hand-picked image per size: the small SVG (no spark, the
pick larger) for 16-32 px, where detail turns into noise, and the full one
above. Run after changing either SVG:

    python assets/make_icon.py

Needs Playwright's Chromium (to draw the SVG exactly as a browser does) and
Pillow; neither is needed to BUILD RockForge, only to remake the icon.
"""

from __future__ import annotations

import io
import os
import shutil
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SMALL = (16, 20, 24, 32)
LARGE = (40, 48, 64, 96, 128, 256)


def render(svg: str, size: int, page) -> Image.Image:  # type: ignore[no-untyped-def]
    sized = svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f'<html><body style="margin:0;background:transparent">{sized}</body></html>')
    return Image.open(io.BytesIO(page.screenshot(omit_background=True))).convert("RGBA")


def main() -> None:
    small = (HERE / "rockforge-small.svg").read_text(encoding="utf-8")
    large = (HERE / "rockforge.svg").read_text(encoding="utf-8")
    chromium = os.environ.get("ROCKFORGE_CHROMIUM") or (
        "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium)
        page = browser.new_page()
        images = [render(small, s, page) for s in SMALL] + [render(large, s, page) for s in LARGE]
        browser.close()
    biggest = images[-1]
    biggest.save(HERE / "rockforge-256.png")
    biggest.save(
        HERE / "rockforge.ico",
        sizes=[im.size for im in images],
        append_images=images[:-1],
    )
    shutil.copyfile(HERE / "rockforge-small.svg", HERE.parent / "web" / "favicon.svg")


if __name__ == "__main__":
    main()
