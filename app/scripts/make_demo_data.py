"""Generate the SYNTHETIC DEMO data set in app/public/data/.

Everything here is a plain flat-colour placeholder with a text label. It is not
radar, it is not derived from NISAR, and it depicts no real place. It exists so
the app can be run and tested before real data is available.

Run from the repo root:  python app/scripts/make_demo_data.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "public" / "data"
SIZE = 512
DATES = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19"]
# Flat tints: cool for HH, warm for HV, getting lighter with each date so a change is visible.
TINT = {"HH": (30, 90, 100), "HV": (110, 80, 30)}


def label(img: Image.Image, lines: list[str]) -> None:
    d = ImageDraw.Draw(img)
    y = 24
    for line in lines:
        d.text((24, y), line, fill=(255, 255, 255))
        y += 16


def frame(pol: str, i: int, date: str) -> Image.Image:
    r, g, b = TINT[pol]
    k = 1 + 0.35 * i
    img = Image.new("RGB", (SIZE, SIZE), (min(int(r * k), 255), min(int(g * k), 255), min(int(b * k), 255)))
    ImageDraw.Draw(img).rectangle([0, 0, SIZE - 1, SIZE - 1], outline=(255, 255, 255), width=4)
    label(img, ["SYNTHETIC DEMO", "NOT NISAR DATA", f"placeholder {pol} {date}"])
    return img


def main() -> None:
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    dates = []
    for i, date in enumerate(DATES):
        frames = {}
        for pol in ("HH", "HV"):
            rel = f"frames/{date}_{pol}.webp"
            frame(pol, i, date).save(OUT / rel, "WEBP", quality=60)
            frames[pol] = rel
        dates.append({"date": date, "granule": f"synthetic-demo-{i + 1}", "frames": frames})

    # Composite placeholder: three flat colour bands, red / green / blue.
    comp = Image.new("RGB", (SIZE, SIZE))
    d = ImageDraw.Draw(comp)
    for j, colour in enumerate([(150, 40, 40), (40, 130, 60), (50, 70, 160)]):
        d.rectangle([j * SIZE // 3, 0, (j + 1) * SIZE // 3, SIZE], fill=colour)
    label(comp, ["SYNTHETIC DEMO", "NOT NISAR DATA", "placeholder composite"])
    comp.save(OUT / "frames" / "composite_HH.webp", "WEBP", quality=60)

    manifest = {
        "stack": "synthetic-demo",
        "crid": "none",
        "maturity": "Synthetic demo",
        "bounds": [0.0, 0.0, 1.0, 1.0],
        "dates": dates,
        "composite": "frames/composite_HH.webp",
        # The permanent NISAR data gap. This is a verified fact, not a placeholder.
        "gap": {"start": "2026-07-27T22:03:25Z", "end": "2026-08-10T00:55:27Z"},
        "stretch_db": {"HH": [0, 1], "HV": [0, 1]},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(dates) * 2 + 1} images and manifest.json to {OUT}")


if __name__ == "__main__":
    main()
