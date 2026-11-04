"""ElevenLabs client for the video scripts.

The key lives in the repo's .env.local (git-ignored, written by `elevenlabs onboard`) and is read into
ELEVENLABS_API_KEY here; it is never printed or stored in code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

VOICE_ALICE = "Xb7hH8MSUJpSbSDYk0k2"
MODEL = "eleven_multilingual_v2"


def client() -> ElevenLabs:
    # the SDK's default reads the env at import time, before load_dotenv ran, so pass it explicitly
    return ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])


def speak(text: str, out: Path, speed: float = 1.0, voice: str = VOICE_ALICE) -> Path:
    """Voice `text` with Alice into an mp3 at `out`."""
    audio = client().text_to_speech.convert(
        voice_id=voice, model_id=MODEL, text=text, output_format="mp3_44100_128",
        voice_settings={"stability": 0.5, "similarity_boost": 0.75, "speed": speed})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    return out


def transcribe(path: Path) -> str:
    """Speech-to-text for a local audio or video file."""
    with open(path, "rb") as f:
        return client().speech_to_text.convert(file=f, model_id="scribe_v1").text
