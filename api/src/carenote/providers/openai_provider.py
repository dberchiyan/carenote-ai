"""OpenAI extraction (structured output) and transcription."""

import io
import time

import openai

from carenote.contracts.extraction import Extraction
from carenote.contracts.llm import (
    ExtractionResult,
    LLMUsage,
    Prompt,
    ProviderError,
    TranscriptionResult,
)
from carenote.providers.pricing import TRANSCRIPTION_PRICE_PER_MIN, llm_cost

DEFAULT_LLM_MODEL = "gpt-5-mini"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"


class OpenAILLM:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_LLM_MODEL,
        client: openai.OpenAI | None = None,
        timeout_s: float = 45,
        max_retries: int = 1,
    ) -> None:
        self.model = model
        self.client = client or openai.OpenAI(
            api_key=api_key, max_retries=max_retries, timeout=timeout_s
        )

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        started = time.perf_counter()
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=prompt.system,
                input=f"<note>\n{redacted_text}\n</note>",
                text_format=Extraction,
            )
        except openai.APIStatusError as exc:
            raise ProviderError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("Could not reach the OpenAI API") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)

        if response.output_parsed is None:
            raise ProviderError("The model returned no usable structured output")
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        return ExtractionResult(
            extraction=response.output_parsed,
            usage=LLMUsage(
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=llm_cost(response.model, input_tokens, output_tokens),
                latency_ms=latency_ms,
            ),
        )


class OpenAITranscription:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_TRANSCRIPTION_MODEL,
        client: openai.OpenAI | None = None,
        timeout_s: float = 45,
        max_retries: int = 1,
    ) -> None:
        self.model = model
        self.client = client or openai.OpenAI(
            api_key=api_key, max_retries=max_retries, timeout=timeout_s
        )

    def transcribe(
        self, audio: bytes, filename: str, content_type: str, duration_s: float | None = None
    ) -> TranscriptionResult:
        started = time.perf_counter()
        try:
            result = self.client.audio.transcriptions.create(
                model=self.model,
                file=(filename, io.BytesIO(audio), content_type),
                # Vocabulary hint; contains no patient data.
                prompt="Nursing shift note with vital signs, medications and abbreviations "
                "such as BP, HR, RR, SpO2, PO, IV, b.i.d.",
            )
        except openai.APIStatusError as exc:
            raise ProviderError(f"OpenAI API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("Could not reach the OpenAI API") from exc
        minutes = (duration_s or 0) / 60
        return TranscriptionResult(
            text=result.text,
            model=self.model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            cost_usd=round(minutes * TRANSCRIPTION_PRICE_PER_MIN.get(self.model, 0.0), 6),
        )
