"""Audio for the eval dataset: TTS with several voices, plus background noise on some files.

TTS providers:
  macos   — the built-in `say` command (no API key; macOS only)
  openai  — OpenAI speech API (needs CARENOTE_OPENAI_API_KEY)
"""

from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise

if TYPE_CHECKING:
    from evals.generate import Case

OPENAI_VOICES = {"Samantha": "nova", "Daniel": "onyx", "Karen": "shimmer"}


class TTSProvider(Protocol):
    def synthesize(self, text: str, voice: str, out_path: Path) -> None: ...


class MacOSSay:
    def __init__(self) -> None:
        if shutil.which("say") is None or shutil.which("afconvert") is None:
            raise RuntimeError("The macos TTS provider needs macOS (`say` and `afconvert`).")

    def synthesize(self, text: str, voice: str, out_path: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "speech.aiff"
            subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)  # noqa: S603, S607
            subprocess.run(  # noqa: S603
                ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(aiff), str(out_path)],  # noqa: S607
                check=True,
            )


class OpenAITTS:
    def __init__(self) -> None:
        from openai import OpenAI

        from carenote.config import get_settings

        key = get_settings().openai_api_key
        if key is None:
            raise RuntimeError("CARENOTE_OPENAI_API_KEY is required for the openai TTS provider.")
        self.client = OpenAI(api_key=key.get_secret_value())

    def synthesize(self, text: str, voice: str, out_path: Path) -> None:
        response = self.client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=OPENAI_VOICES.get(voice, "alloy"),
            input=text,
            response_format="wav",
        )
        out_path.write_bytes(response.content)


def ward_noise(duration_ms: int, rng: random.Random) -> AudioSegment:
    """Synthetic ward ambience: hiss plus an occasional monitor beep."""
    noise = WhiteNoise().to_audio_segment(duration=duration_ms, volume=-34 + rng.uniform(-4, 4))
    beep = Sine(rng.choice((880, 1000, 1200))).to_audio_segment(duration=120, volume=-26)
    for start in range(rng.randrange(300, 900), duration_ms, rng.randrange(900, 1600)):
        noise = noise.overlay(beep, position=start)
    return noise


def add_noise(path: Path, rng: random.Random) -> None:
    speech = AudioSegment.from_wav(path)
    speech.overlay(ward_noise(len(speech), rng)).export(path, format="wav")


def synthesize_all(cases: list[Case], out_dir: Path, provider: str, seed: int) -> None:
    tts: TTSProvider = MacOSSay() if provider == "macos" else OpenAITTS()
    rng = random.Random(seed)  # noqa: S311 - synthetic data
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        path = out_dir / f"{case.id}.wav"
        tts.synthesize(case.text, case.voice, path)
        if "background_noise" in case.tags:
            add_noise(path, rng)
        print(f"  {path.name} ({case.voice}{', noise' if 'background_noise' in case.tags else ''})")
