"""Assemble the final video: picture + voice per segment, joined, with subtitles burned in and an .srt."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"
SEG = OUT / "segments"
SEG.mkdir(exist_ok=True)
FINAL = OUT / "SARtale-explainer.mp4"
SCENE = {"01_hook": "S01", "02_radar": "S02", "03_curve": "S03", "04_step": "S04", "05_rule": "S05",
         "06_shuffle": "S06", "07_missed": "S07", "09_close": "S09"}
PAD = 0.6

n = json.load(open(ROOT / "narration.json", encoding="utf8"))
subs = json.load(open(ROOT / "subtitles.json", encoding="utf8"))
dur = json.load(open(OUT / "durations.json", encoding="utf8"))


def run(*a):
    subprocess.run(a, check=True)


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


parts, lines, t0, idx = [], [], 0.0, 1
for seg in n["segments"]:
    i, d = seg["id"], dur[seg["id"]]
    target = SEG / f"{i}.mp4"
    if i in SCENE:
        pic = ["-i", str(OUT / "media" / "videos" / "scenes" / "1080p30" / f"{SCENE[i]}.mp4")]
        vf = "tpad=stop_mode=clone:stop_duration=2,fps=30,scale=out_color_matrix=bt709:out_range=tv,setsar=1"
    else:
        pic = ["-framerate", "12", "-i", str(OUT / "app" / i / "%05d.jpg")]
        vf = "scale=1920:1080:in_range=pc:out_range=tv:out_color_matrix=bt709,tpad=stop_mode=clone:stop_duration=2,fps=30,setsar=1"
    run("ffmpeg", "-v", "error", "-y", *pic, "-i", str(OUT / "audio" / f"{i}.mp3"),
        "-filter_complex", f"[0:v]{vf},format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{d}", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(target))
    parts.append(target)
    cues = subs[i]
    weights = [len(c.replace("\n", " ")) + 6 for c in cues]
    speech, at = d - PAD, 0.0
    for c, w in zip(cues, weights):
        span = speech * w / sum(weights)
        lines.append(f"{idx}\n{ts(t0 + at)} --> {ts(t0 + at + span - 0.04)}\n{c}\n")
        at, idx = at + span, idx + 1
    t0 += d

srt = OUT / "SARtale-explainer.srt"
srt.write_text("\n".join(lines), encoding="utf8")
lst = OUT / "list.txt"
lst.write_text("".join(f"file 'segments/{p.name}'\n" for p in parts), encoding="utf8")
run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(OUT / "joined.mp4"))
print(FINAL, round(t0, 1), "s", idx - 1, "cues")
