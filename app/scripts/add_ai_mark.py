"""Stamp the team logo without redrawing it or modifying the favicon.

Run from any directory: python app/scripts/add_ai_mark.py
The first run preserves the master byte-for-byte as SARtale-original.png.
Keep that original: subsequent runs always stamp it, never the marked image.
Only Pillow and the Python standard library are required.
"""
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont

APP = Path(__file__).resolve().parents[1]
MASTER = APP / "logo" / "SARtale.png"
ORIGINAL = MASTER.with_name("SARtale-original.png")
LOGO_256 = APP / "public" / "brand" / "logo-256.png"


def main() -> None:
    # Resolve the font before touching the master or creating the backup.
    fonts = [Path("C:/Windows/Fonts/arialbd.ttf"),
             Path("C:/Windows/Fonts/segoeuib.ttf")]
    font_path = next((path for path in fonts if path.is_file()), None)
    if font_path is None:
        raise FileNotFoundError("Arial Bold or Segoe UI Bold is required in C:/Windows/Fonts")
    if not ORIGINAL.exists():
        shutil.copy2(MASTER, ORIGINAL)
    with Image.open(ORIGINAL) as source:
        logo = source.convert("RGBA")

    scale = logo.width / 1254
    font = ImageFont.truetype(str(font_path), round(90 * scale))
    label = "AI-generated"
    left, top, right, bottom = font.getbbox(label)
    pad_x, pad_y = round(16 * scale), round(10 * scale)
    width = right - left + 2 * pad_x
    height = bottom - top + 2 * pad_y
    # Empty upper-right corner, above the radar ring and beside the satellite.
    x, y = logo.width - width - round(16 * scale), round(16 * scale)
    overlay = Image.new("RGBA", logo.size)
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((x, y, x + width - 1, y + height - 1),
                           radius=round(16 * scale), fill=(5, 13, 22, 204))
    draw.text((x + pad_x - left, y + pad_y - top), label,
              font=font, fill=(233, 241, 246, 255))
    stamped = Image.alpha_composite(logo, overlay)
    stamped.save(MASTER, optimize=True)
    # Same RGBA / LANCZOS / optimized PNG pipeline as make_brand_assets.py.
    # Deliberately do not call that script: it also rewrites the favicon.
    stamped.resize((256, 256), Image.Resampling.LANCZOS).save(LOGO_256, optimize=True)
    print(MASTER)
    print(LOGO_256)


if __name__ == "__main__":
    main()
