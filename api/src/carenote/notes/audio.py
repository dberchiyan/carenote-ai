"""Audio upload checks: size, declared type, actual file signature and duration."""

import re
import shutil
import subprocess
import wave
from io import BytesIO
from pathlib import Path

# Declared MIME type -> file extension. MediaRecorder gives webm (Chrome/Firefox) or mp4 (Safari).
ALLOWED_TYPES = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


class AudioRejectedError(ValueError):
    pass


def base_type(content_type: str | None) -> str:
    return (content_type or "").split(";")[0].strip().lower()


def sniff(data: bytes) -> str | None:
    """Container format from magic bytes; never trust the declared type alone."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    if data[4:8] == b"ftyp":
        return "m4a"
    return None


def _ffprobe_duration(path: Path) -> float | None:
    if shutil.which("ffprobe") is None:
        return None
    out = subprocess.run(  # noqa: S603
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],  # noqa: S607
        capture_output=True, text=True, timeout=20, check=False,
    )  # fmt: skip
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def _decode_duration(path: Path) -> float | None:
    """MediaRecorder webm files often carry no duration header: decode and read the clock."""
    if shutil.which("ffmpeg") is None:
        return None
    out = subprocess.run(  # noqa: S603
        ["ffmpeg", "-nostdin", "-i", str(path), "-f", "null", "-"],  # noqa: S607
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", out.stderr)
    if not times:
        return None
    h, m, s = times[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def duration_seconds(path: Path, data: bytes, kind: str) -> float:
    if kind == "wav":
        try:
            with wave.open(BytesIO(data)) as w:
                frames: int = w.getnframes()
                return frames / float(w.getframerate())
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise AudioRejectedError("The WAV file could not be read.") from exc
    duration = _ffprobe_duration(path) or _decode_duration(path)
    if duration is None:
        raise AudioRejectedError("Could not determine the recording's length.")
    return duration


def validate_upload(data: bytes, content_type: str | None, max_bytes: int) -> str:
    """Return the file extension to store, or raise AudioRejectedError."""
    if not data:
        raise AudioRejectedError("The file is empty.")
    if len(data) > max_bytes:
        raise AudioRejectedError(f"The file is larger than {max_bytes // (1024 * 1024)} MB.")
    declared = ALLOWED_TYPES.get(base_type(content_type))
    if declared is None:
        raise AudioRejectedError("Unsupported file type. Use WebM, WAV, MP3 or M4A audio.")
    actual = sniff(data)
    if actual is None or actual != declared:
        raise AudioRejectedError("The file content does not match its type.")
    return actual
