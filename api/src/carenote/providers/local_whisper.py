"""Local transcription with Whisper (faster-whisper / CTranslate2) on the CPU.

Nothing leaves the machine and no key is needed, which makes it the right default for the demo:
the keyless `fake` provider never looks at the audio. Audio is decoded with ffmpeg (already in
the image for duration checks) into 16 kHz mono samples, so MediaRecorder's webm/opus works
without depending on PyAV. The model loads lazily on the first note and is then kept.
"""

import logging
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from carenote.contracts.llm import ProviderError, TranscriptionResult

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FFMPEG_DECODE = ("ffmpeg", "-v", "error", "-nostdin", "-i")
# Vocabulary hint for the decoder; contains no patient data.
PROMPT = (
    "Nursing shift note: patient name, blood pressure, pulse, temperature, "
    "oxygen saturation, respiratory rate, symptoms, medications."
)


class WhisperLike(Protocol):
    """The slice of `faster_whisper.WhisperModel` we use; tests pass a stub."""

    def transcribe(self, audio: Any, **options: Any) -> tuple[Any, Any]: ...


def decode_audio(data: bytes, suffix: str) -> np.ndarray[Any, np.dtype[np.float32]]:
    """Any container ffmpeg reads -> float32 mono at 16 kHz."""
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(data)
        tmp.flush()
        command = [
            *FFMPEG_DECODE,
            tmp.name,
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-",
        ]
        try:
            out = subprocess.run(command, capture_output=True, timeout=60, check=False)  # noqa: S603
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError("ffmpeg is not available to decode the recording") from exc
    if out.returncode != 0 or not out.stdout:
        raise ProviderError("The recording could not be decoded")
    return np.frombuffer(out.stdout, dtype=np.float32)


class LocalWhisperTranscription:
    name = "local"

    def __init__(
        self,
        model_name: str = "base.en",
        model_dir: Path | None = None,
        *,
        beam_size: int = 1,
        model: WhisperLike | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_dir = model_dir
        self.beam_size = beam_size
        self._model = model
        self._lock = threading.Lock()

    @property
    def model(self) -> WhisperLike:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                started = time.perf_counter()
                self._model = WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(self.model_dir) if self.model_dir else None,
                )
                log.info(
                    "loaded whisper %s in %d ms",
                    self.model_name,
                    round((time.perf_counter() - started) * 1000),
                )
            return self._model

    def transcribe(
        self, audio: bytes, filename: str, content_type: str, duration_s: float | None = None
    ) -> TranscriptionResult:
        started = time.perf_counter()
        samples = decode_audio(audio, Path(filename).suffix or ".webm")
        try:
            segments, _ = self.model.transcribe(
                samples,
                language="en",
                beam_size=self.beam_size,
                vad_filter=True,
                initial_prompt=PROMPT,
            )
            text = " ".join(s.text.strip() for s in segments)
        except Exception as exc:  # the model raises its own exception types
            raise ProviderError(f"Local transcription failed: {type(exc).__name__}") from exc
        return TranscriptionResult(
            text=text,
            model=f"whisper-{self.model_name}",
            latency_ms=round((time.perf_counter() - started) * 1000),
            cost_usd=0.0,
        )
