"""Copy each voice clip to out/audio/<id>.mp3 and write durations.json, with a short pause after each."""
import glob, json, os, shutil, subprocess

n = json.load(open("narration.json", encoding="utf8"))
s = json.load(open("subtitles.json", encoding="utf8"))
d = {}
for seg in n["segments"]:
    i = seg["id"]
    src = sorted(glob.glob(f"out/audio/{i}/*.mp3"))[-1]
    shutil.copy(src, f"out/audio/{i}.mp3")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True)
    d[i] = round(float(r.stdout) + 0.6, 2)
    joined = " ".join(" ".join(c.split()) for c in s[i])
    if joined != " ".join(seg["text"].split()):
        print("subtitle mismatch fixed by hand needed", i)
        a, b = joined.split(), seg["text"].split()
        print([x for x in zip(a, b) if x[0] != x[1]][:4])
json.dump(d, open("out/durations.json", "w"), indent=1)
print(d, round(sum(d.values())), "s total")
