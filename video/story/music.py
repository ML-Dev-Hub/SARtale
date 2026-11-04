"""Music bed (ElevenLabs music_v2_5, composition plan timed to the story beats) and two sound effects.

Writes out/audio/music.mp3, out/audio/sfx_rumble.mp3, out/audio/sfx_radar.mp3.
Beat lengths follow out/audio/nathaniel_timing.json after the 4% tempo lift in build.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import eleven  # noqa: E402

OUT = HERE / "out" / "audio"
NEG = ["vocals", "singing", "choir", "lyrics", "drums solo", "EDM drop", "distortion"]
STYLE = ["cinematic documentary score", "instrumental only", "76 BPM", "D minor", "wide stereo", "subtle, under narration"]

PLAN = {"chunks": [
    {"text": "[Intro] {low cello drone and distant deep piano notes, tense and sparse, a sense of danger in the mountains}",
     "duration_ms": 6000, "positive_styles": STYLE + ["dark", "ominous", "low strings"], "negative_styles": NEG},
    {"text": "[Build] {a slow heartbeat pulse enters, muted strings rise, uncertainty, clouds gathering}",
     "duration_ms": 7500, "positive_styles": STYLE + ["tension building", "soft pulse", "muted strings"], "negative_styles": NEG},
    {"text": "[Lift] {the tension opens up: a bright shimmering swell, felt piano chord, light breaks through}",
     "duration_ms": 3000, "positive_styles": STYLE + ["uplifting swell", "shimmer", "reveal"], "negative_styles": NEG},
    {"text": "[Drive] {warm, hopeful and determined: steady piano ostinato, soft strings, light ticking percussion, moves forward}",
     "duration_ms": 10000, "positive_styles": STYLE + ["hopeful", "purposeful", "warm piano", "light percussion"], "negative_styles": NEG},
    {"text": "[Resolve] {resolves to F major, a warm closing theme over credits, then a final sustained chord that fades out gently}",
     "duration_ms": 8000, "positive_styles": STYLE + ["resolution", "warm", "gentle fade out"], "negative_styles": NEG},
]}


def save(stream, path):
    path.write_bytes(b"".join(stream))
    print("saved", path.name, path.stat().st_size)


def main():
    c = eleven.client()
    save(c.music.compose(composition_plan=PLAN, model_id="music_v2_5", output_format="mp3_44100_128"), OUT / "music.mp3")
    save(c.text_to_sound_effects.convert(
        text="distant deep rumble of a mountain flood, rushing muddy water and rolling boulders, cinematic, low",
        duration_seconds=6, prompt_influence=0.5), OUT / "sfx_rumble.mp3")
    save(c.text_to_sound_effects.convert(
        text="clean futuristic radar sweep with a soft sonar ping, cinematic reveal whoosh",
        duration_seconds=2.5, prompt_influence=0.5), OUT / "sfx_radar.mp3")


if __name__ == "__main__":
    main()
