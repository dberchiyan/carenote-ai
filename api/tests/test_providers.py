"""Real provider adapters, tested against stubbed SDK clients (no network)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from carenote.config import Settings
from carenote.contracts.extraction import Extraction
from carenote.contracts.llm import ProviderError
from carenote.pipeline.prompts import load_prompt
from carenote.providers.anthropic_llm import AnthropicLLM
from carenote.providers.factory import build_llm, build_transcription
from carenote.providers.fake import FakeTranscription, RuleBasedLLM
from carenote.providers.local_whisper import LocalWhisperTranscription, decode_audio
from carenote.providers.openai_provider import OpenAILLM, OpenAITranscription
from carenote.providers.pricing import llm_cost

EXTRACTION = Extraction(
    patient_mention="<PATIENT_1>",
    vitals=[],
    symptoms=["headache"],
    medications=[],
    free_text_summary="Headache.",
    uncertain=[],
)


class StubAnthropic:
    def __init__(self, response: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))
        self.response = response

    def _parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def anthropic_response(
    stop_reason: str = "end_turn", parsed: Extraction | None = EXTRACTION
) -> Any:
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=parsed,
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
    )


def test_anthropic_sends_redacted_text_with_schema_and_reports_cost() -> None:
    stub = StubAnthropic(anthropic_response())
    provider = AnthropicLLM("key", client=stub)  # type: ignore[arg-type]
    result = provider.extract("<PATIENT_1> has a headache", load_prompt())

    call = stub.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is Extraction
    assert call["system"] == load_prompt().system
    assert "<PATIENT_1> has a headache" in call["messages"][0]["content"]
    assert result.extraction == EXTRACTION
    assert result.usage.input_tokens == 1200
    assert result.usage.cost_usd == pytest.approx(1200 * 4 / 1e6 + 300 * 20 / 1e6)


@pytest.mark.parametrize(
    "response",
    [anthropic_response(stop_reason="refusal"), anthropic_response(parsed=None)],
)
def test_anthropic_unusable_responses_raise_provider_error(response: Any) -> None:
    provider = AnthropicLLM("key", client=StubAnthropic(response))  # type: ignore[arg-type]
    with pytest.raises(ProviderError):
        provider.extract("text", load_prompt())


def test_openai_extraction_and_transcription() -> None:
    calls: list[dict[str, Any]] = []

    def parse(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=EXTRACTION,
            model="gpt-5-mini",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        )

    def transcribe(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(text="Pulse 80.")

    stub = SimpleNamespace(
        responses=SimpleNamespace(parse=parse),
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=transcribe)),
    )
    result = OpenAILLM("key", client=stub).extract("redacted", load_prompt())  # type: ignore[arg-type]
    assert calls[0]["text_format"] is Extraction
    assert result.usage.cost_usd == llm_cost("gpt-5-mini", 1000, 200)

    text = OpenAITranscription("key", client=stub).transcribe(b"RIFF", "a.wav", "audio/wav", 60)  # type: ignore[arg-type]
    assert text.text == "Pulse 80."
    assert text.cost_usd == pytest.approx(0.006)


def test_factory_defaults_to_fake_and_requires_keys_for_real_providers() -> None:
    assert isinstance(build_llm(Settings()), RuleBasedLLM)
    assert isinstance(build_transcription(Settings()), LocalWhisperTranscription)
    assert isinstance(
        build_transcription(Settings(transcription_provider="fake")), FakeTranscription
    )
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        build_llm(Settings(llm_provider="anthropic", anthropic_api_key=None))


def test_unknown_model_costs_nothing_but_says_so(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="carenote.providers.pricing"):
        assert llm_cost("some-future-model", 1000, 1000) == 0.0
    assert "some-future-model" in caplog.text
    assert "no price" in caplog.text


def test_cost_follows_the_model_that_answered() -> None:
    """A server-side fallback answers with another model: price that one, not the requested."""
    response = anthropic_response()
    response.model = "claude-haiku-4-5"
    provider = AnthropicLLM("key", client=StubAnthropic(response))  # type: ignore[arg-type]
    result = provider.extract("text", load_prompt())
    assert result.usage.model == "claude-haiku-4-5"
    assert result.usage.cost_usd == pytest.approx(llm_cost("claude-haiku-4-5", 1200, 300))


def test_rule_based_llm_records_requests_only_when_asked() -> None:
    silent, spy = RuleBasedLLM(), RuleBasedLLM(record=True)
    for llm in (silent, spy):
        llm.extract("<PATIENT_1>, pulse 80", load_prompt())
    assert silent.requests == []
    assert len(spy.requests) == 1
    runtime = build_llm(Settings())
    assert isinstance(runtime, RuleBasedLLM)
    assert not runtime.record


def test_empty_env_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from carenote.config import DEV_SESSION_SECRET

    monkeypatch.setenv("CARENOTE_SESSION_SECRET", "")
    monkeypatch.setenv("CARENOTE_ANTHROPIC_API_KEY", "")
    settings = Settings()
    assert settings.session_secret.get_secret_value() == DEV_SESSION_SECRET
    assert settings.anthropic_api_key is None


def test_prod_requires_a_real_session_secret() -> None:
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        Settings(env="prod")


class StubWhisper:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: Any, **options: Any) -> tuple[Any, Any]:
        self.calls.append({"samples": len(audio), **options})
        return iter(
            [SimpleNamespace(text=" Mrs. Anna Keller, "), SimpleNamespace(text="pulse 72.")]
        ), None


FIXTURES = Path(__file__).parent / "fixtures"


def test_local_whisper_decodes_with_ffmpeg_and_joins_segments() -> None:
    """The model is not loaded in unit tests; decoding and the result shape are what we own."""
    stub = StubWhisper()
    provider = LocalWhisperTranscription(model=stub)
    data = (FIXTURES / "note.webm").read_bytes()
    result = provider.transcribe(data, "note.webm", "audio/webm", 4.75)
    assert result.text == "Mrs. Anna Keller, pulse 72."
    assert result.model == "whisper-base.en"
    assert result.cost_usd == 0.0
    call = stub.calls[0]
    assert 4 * 16_000 < call["samples"] < 6 * 16_000  # ~4.75 s at 16 kHz mono
    assert call["language"] == "en"
    assert call["vad_filter"] is True
    assert "patient" not in call["initial_prompt"].lower() or "name" in call["initial_prompt"]


def test_local_whisper_rejects_undecodable_audio() -> None:
    with pytest.raises(ProviderError, match="decoded"):
        decode_audio(b"not audio at all", ".webm")


@pytest.mark.integration
def test_local_whisper_transcribes_the_fixture_for_real() -> None:
    """Downloads base.en on first run; run with `-m integration`."""
    result = LocalWhisperTranscription().transcribe(
        (FIXTURES / "note.wav").read_bytes(), "note.wav", "audio/wav", 4.75
    )
    assert "keller" in result.text.lower()
    assert "150" in result.text
