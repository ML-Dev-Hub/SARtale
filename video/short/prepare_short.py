"""Write out/durations.json from the voiced clips in out/audio/<id>.mp3, with a short pause after each."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
n = json.load(open(HERE / "narration.json", encoding="utf8"))
d = {}
for seg in n["segments"]:
    a = HERE / "out" / "audio" / f"{seg['id']}.mp3"
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(a)],
                       capture_output=True, text=True, check=True)
    d[seg["id"]] = round(float(r.stdout) + 0.35, 2)
json.dump(d, open(HERE / "out" / "durations.json", "w"), indent=1)
print(d, round(sum(d.values()), 1), "s total")
