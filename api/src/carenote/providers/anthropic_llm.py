"""Anthropic Claude extraction with structured output (Pydantic schema -> JSON schema)."""

import time
from typing import Literal

import anthropic

from carenote.contracts.extraction import Extraction
from carenote.contracts.llm import ExtractionResult, LLMUsage, Prompt, ProviderError
from carenote.providers.pricing import llm_cost

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicLLM:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium",
        client: anthropic.Anthropic | None = None,
        timeout_s: float = 45,
        max_retries: int = 1,
    ) -> None:
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic(
            api_key=api_key, max_retries=max_retries, timeout=timeout_s
        )

    def extract(self, redacted_text: str, prompt: Prompt) -> ExtractionResult:
        started = time.perf_counter()
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=prompt.system,
                messages=[{"role": "user", "content": f"<note>\n{redacted_text}\n</note>"}],
                output_format=Extraction,
                output_config={"effort": self.effort},
                # Route policy declines to a fallback model inside the same call.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Could not reach the Anthropic API") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)

        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to process this note")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ProviderError("The model returned no usable structured output")

        usage = response.usage
        return ExtractionResult(
            extraction=response.parsed_output,
            usage=LLMUsage(
                model=response.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=llm_cost(response.model, usage.input_tokens, usage.output_tokens),
                latency_ms=latency_ms,
            ),
        )
