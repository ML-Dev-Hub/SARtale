"""Resize the team logo into the small web versions in app/public/brand/.

The source, app/logo/SARtale.png, is committed unchanged. This script only
scales it down (no redraw, no recolour, no crop). Run from the repo root:

    python app/scripts/make_brand_assets.py
"""
from pathlib import Path

from PIL import Image

APP = Path(__file__).resolve().parents[1]
SOURCE = APP / "logo" / "SARtale.png"
OUT = APP / "public" / "brand"

# name -> edge length in pixels (the logo is square)
SIZES = {"logo-256.png": 256, "favicon-64.png": 64}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = Image.open(SOURCE).convert("RGBA")
    for name, size in SIZES.items():
        src.resize((size, size), Image.Resampling.LANCZOS).save(OUT / name, optimize=True)
        print(OUT / name)


if __name__ == "__main__":
    main()
