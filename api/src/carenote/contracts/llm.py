"""Provider interfaces. Pipeline code depends only on these protocols, never on a vendor SDK."""

from dataclasses import dataclass
from typing import Protocol

from carenote.contracts.extraction import Extraction


class ProviderError(Exception):
    """A provider call failed in a way the pipeline should report to the nurse."""


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str


@dataclass(frozen=True)
class LLMUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


@dataclass(frozen=True)
class ExtractionResult:
    extraction: Extraction
    usage: LLMUsage


class LLMProvider(Protocol):
    name: str

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        """Extract structured data. `redacted_text` must already be free of PII."""
        ...


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model: str
    latency_ms: int
    cost_usd: float


class TranscriptionProvider(Protocol):
    name: str

    def transcribe(
        self, audio: bytes, filename: str, content_type: str, duration_s: float | None = None
    ) -> TranscriptionResult: ...
