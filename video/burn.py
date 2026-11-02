"""Burn subtitles into out/joined.mp4 using image overlays, because this ffmpeg has no libass."""
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "out"
SUBS = OUT / "subs"
SUBS.mkdir(exist_ok=True)
font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 38)


def secs(s):
    h, m, r = s.split(":")
    a, b = r.split(",")
    return int(h) * 3600 + int(m) * 60 + int(a) + int(b) / 1000


blocks = (OUT / "SARtale-explainer.srt").read_text(encoding="utf8").strip().split("\n\n")
cues = []
for b in blocks:
    ln = b.split("\n")
    start, end = [secs(x.strip()) for x in ln[1].split("-->")]
    cues.append((start, end, ln[2:]))

probe = Image.new("RGBA", (10, 10))
d = ImageDraw.Draw(probe)
for i, (_, _, lines) in enumerate(cues):
    text = "\n".join(lines)
    box = d.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    w, h = int(box[2] - box[0]) + 56, int(box[3] - box[1]) + 34
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(6, 10, 14, 205))
    dr.multiline_text((28 - box[0], 17 - box[1]), text, font=font, fill=(245, 248, 250, 255), spacing=8, align="center")
    im.save(SUBS / f"{i:03d}.png")

inputs, chain, last = ["-i", "joined.mp4"], [], "0:v"
for i, (s, e, _) in enumerate(cues):
    inputs += ["-i", f"subs/{i:03d}.png"]
    chain.append(f"[{last}][{i + 1}:v]overlay=x=(W-w)/2:y=H-h-34:enable='between(t,{s:.3f},{e:.3f})':eof_action=repeat[v{i}]")
    last = f"v{i}"
(OUT / "subs.filter").write_text(";\n".join(chain), encoding="utf8")
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex_script", "subs.filter", "-map", f"[{last}]", "-map", "0:a",
                "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-c:a", "copy", "-movflags", "+faststart",
                "SARtale-explainer.mp4"], check=True, cwd=OUT)
print("done", len(cues))
