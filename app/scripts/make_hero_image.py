"""Make the small picture behind the opening screen from the seasonal composite.

The composite frame (app/public/data/frames/composite_HH.webp) is about 1.7 MB, too heavy for the first screen. This
writes a scaled-down copy to app/public/brand/hero-radar.webp. It scales and re-compresses only: no redraw, no recolour,
no crop. The data frames themselves are not touched. Run from the repo root:

    python app/scripts/make_hero_image.py
"""
from pathlib import Path

from PIL import Image

APP = Path(__file__).resolve().parents[1]
SOURCE = APP / "public" / "data" / "frames" / "composite_HH.webp"
OUT = APP / "public" / "brand" / "hero-radar.webp"
WIDTH = 1280


def main() -> None:
    src = Image.open(SOURCE).convert("RGBA")
    height = round(src.height * WIDTH / src.width)
    small = src.resize((WIDTH, height), Image.Resampling.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    small.save(OUT, "WEBP", quality=56, method=6)
    print(OUT, small.size, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
