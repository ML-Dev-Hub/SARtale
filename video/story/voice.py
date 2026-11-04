"""Voice script.json in one eleven_v4 request per narrator (one take keeps the emotion continuous) and
find where each shot starts from the character timestamps.

Usage: voice.py [narrator ...]   (default: all in script.json)
Writes out/audio/<narrator>.mp3 and out/audio/<narrator>_timing.json ({shot id: [start_s, end_s]}).
"""
import base64
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import eleven  # noqa: E402

OUT = HERE / "out" / "audio"
OUT.mkdir(parents=True, exist_ok=True)
S = json.load(open(HERE / "script.json", encoding="utf8"))


def spoken(text):
    return re.sub(r"\[[^\]]*\]\s*", "", text).strip()


def main(names):
    full = " ".join(s["text"] for s in S["shots"])
    c = eleven.client()
    for name in names:
        r = c.text_to_speech.convert_with_timestamps(
            voice_id=S["voices"][name], model_id=S["model"], text=full, output_format="mp3_44100_128",
            voice_settings={"stability": 0.5, "similarity_boost": 0.75})
        (OUT / f"{name}.mp3").write_bytes(base64.b64decode(r.audio_base_64))
        al = r.alignment
        chars, starts, ends = al.characters, al.character_start_times_seconds, al.character_end_times_seconds
        said = "".join(chars)
        timing, pos = {}, 0
        for s in S["shots"]:
            words = spoken(s["text"])
            i = said.find(words[:12], pos)
            j = i + len(words)
            if i < 0:
                raise SystemExit(f"{name}: cannot find shot {s['id']} in alignment")
            timing[s["id"]] = [round(starts[i], 3), round(ends[min(j, len(ends)) - 1], 3)]
            pos = j
        json.dump(timing, open(OUT / f"{name}_timing.json", "w"), indent=1)
        print(name, round(ends[-1], 2), "s", timing)


if __name__ == "__main__":
    main(sys.argv[1:] or list(S["voices"]))
