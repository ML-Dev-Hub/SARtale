"""Make narration.json match Codex's corrected subtitle wording, then check scene cue phrases."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
n = json.load(open(ROOT / "narration.json", encoding="utf8"))
s = json.load(open(ROOT / "subtitles.json", encoding="utf8"))
for k, cues in s.items():
    cues[:] = [c.replace("Every monsoon, the rivers", "In the monsoon, the rivers") for c in cues]
json.dump(s, open(ROOT / "subtitles.json", "w", encoding="utf8"), indent=1, ensure_ascii=False)
for seg in n["segments"]:
    new = " ".join(c.replace("\n", " ") for c in s[seg["id"]])
    new = re.sub(r"\s+", " ", new).strip()
    if new != seg["text"]:
        a, b = seg["text"].split(), new.split()
        print(seg["id"], "changed", len(a), "->", len(b))
    seg["text"] = new
json.dump(n, open(ROOT / "narration.json", "w", encoding="utf8"), indent=2, ensure_ascii=False)
for seg in n["segments"]:
    print(seg["id"], len(seg["text"].split()), "words", len(s[seg["id"]]), "cues", "max line", max(len(l) for c in s[seg["id"]] for l in c.split("\n")))
src = (ROOT / "scenes.py").read_text(encoding="utf8")
texts = {x["id"]: x["text"] for x in n["segments"]}
for cls in re.split(r"\nclass ", src)[1:]:
    m = re.search(r'seg = "(\w+)"', cls)
    if not m or not m.group(1) in texts:
        continue
    for p in re.findall(r'self\.at\("([^"]+)"\)', cls):
        if p not in texts[m.group(1)]:
            print("MISSING cue", m.group(1), repr(p))
print(sum(len(x["text"].split()) for x in n["segments"]), "words total")
print(texts["02_radar"][:420])
print(texts["05_rule"])
