"""Assemble the 30-second demo: app frames + voice per segment, joined, subtitles burned in as image overlays, plus an .srt."""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SEG = OUT / "segments"
SUBS = OUT / "subs"
SEG.mkdir(exist_ok=True)
SUBS.mkdir(exist_ok=True)
FINAL = OUT / "SARtale-lake-watch-30s.mp4"
PAD = 0.35
FONT = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 40)

n = json.load(open(HERE / "narration.json", encoding="utf8"))
dur = json.load(open(OUT / "durations.json", encoding="utf8"))


def run(*a, cwd=None):
    subprocess.run(a, check=True, cwd=cwd)


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cues_for(text, limit=62):
    """Split narration into subtitle cues at sentence, colon, semicolon or comma breaks, each at most `limit` characters."""
    parts = [p.strip() for p in re.split(r"(?<=[.:;])\s+|(?<=,)\s+(?=each|limits|with)", text) if p.strip()]
    out = []
    for p in parts:
        words, line = p.split(), ""
        for w in words:
            if line and len(line) + 1 + len(w) > limit:
                out.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        out.append(line)
    return out


parts, cues, t0 = [], [], 0.0
for seg in n["segments"]:
    i, d = seg["id"], dur[seg["id"]]
    target = SEG / f"{i}.mp4"
    run("ffmpeg", "-v", "error", "-y", "-framerate", "12", "-i", str(OUT / "app" / i / "%05d.jpg"), "-i", str(OUT / "audio" / f"{i}.mp3"),
        "-filter_complex", "[0:v]scale=1920:1080:in_range=pc:out_range=tv:out_color_matrix=bt709,tpad=stop_mode=clone:stop_duration=2,fps=30,setsar=1,"
        "format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{d}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(target))
    parts.append(target)
    cs = cues_for(seg["text"])
    weights = [len(c) + 6 for c in cs]
    speech, at = d - PAD, 0.0
    for c, w in zip(cs, weights):
        span = speech * w / sum(weights)
        cues.append((t0 + at, t0 + at + span - 0.04, c))
        at += span
    t0 += d

srt = "\n".join(f"{k + 1}\n{ts(s)} --> {ts(e)}\n{c}\n" for k, (s, e, c) in enumerate(cues))
(OUT / "SARtale-lake-watch-30s.srt").write_text(srt, encoding="utf8")
(OUT / "list.txt").write_text("".join(f"file 'segments/{p.name}'\n" for p in parts), encoding="utf8")
run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4", cwd=OUT)

probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
inputs, chain, last = ["-i", "joined.mp4"], [], "0:v"
for k, (s, e, text) in enumerate(cues):
    box = probe.textbbox((0, 0), text, font=FONT)
    w, h = int(box[2] - box[0]) + 56, int(box[3] - box[1]) + 34
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(6, 10, 14, 215))
    dr.text((28 - box[0], 17 - box[1]), text, font=FONT, fill=(245, 248, 250, 255))
    im.save(SUBS / f"{k:03d}.png")
    inputs += ["-i", f"subs/{k:03d}.png"]
    chain.append(f"[{last}][{k + 1}:v]overlay=x=(W-w)/2:y=H-h-70:enable='between(t,{s:.3f},{e:.3f})':eof_action=repeat[v{k}]")
    last = f"v{k}"
(OUT / "subs.filter").write_text(";\n".join(chain), encoding="utf8")
run("ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex_script", "subs.filter", "-map", f"[{last}]", "-map", "0:a",
    "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
    "-color_trc", "bt709", "-color_range", "tv", "-c:a", "copy", "-movflags", "+faststart", FINAL.name, cwd=OUT)
print(FINAL, round(t0, 1), "s", len(cues), "cues")
for s, e, c in cues:
    print(f"{s:5.1f}-{e:5.1f} {c}")
