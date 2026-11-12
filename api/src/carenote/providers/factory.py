"""Build providers from settings. The only place that knows about concrete vendors."""

from functools import cache

from carenote.config import Settings, get_settings
from carenote.contracts.llm import LLMProvider, ProviderError, TranscriptionProvider


def _require(key: object, name: str) -> str:
    from pydantic import SecretStr

    if not isinstance(key, SecretStr):
        raise ProviderError(f"{name} is not set")
    return key.get_secret_value()


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from carenote.providers.anthropic_llm import AnthropicLLM

        return AnthropicLLM(
            _require(settings.anthropic_api_key, "CARENOTE_ANTHROPIC_API_KEY"),
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
            timeout_s=settings.provider_timeout_s,
            max_retries=settings.provider_max_retries,
        )
    if settings.llm_provider == "openai":
        from carenote.providers.openai_provider import OpenAILLM

        return OpenAILLM(
            _require(settings.openai_api_key, "CARENOTE_OPENAI_API_KEY"),
            model=settings.openai_model,
            timeout_s=settings.provider_timeout_s,
            max_retries=settings.provider_max_retries,
        )
    from carenote.providers.fake import RuleBasedLLM

    return RuleBasedLLM()


def build_transcription(settings: Settings) -> TranscriptionProvider:
    if settings.transcription_provider == "openai":
        from carenote.providers.openai_provider import OpenAITranscription

        return OpenAITranscription(
            _require(settings.openai_api_key, "CARENOTE_OPENAI_API_KEY"),
            model=settings.openai_transcription_model,
            timeout_s=settings.provider_timeout_s,
            max_retries=settings.provider_max_retries,
        )
    if settings.transcription_provider == "local":
        from carenote.providers.local_whisper import LocalWhisperTranscription

        return LocalWhisperTranscription(settings.local_whisper_model, settings.local_whisper_dir)
    from carenote.providers.fake import FakeTranscription

    return FakeTranscription()


@cache
def get_llm() -> LLMProvider:
    return build_llm(get_settings())


@cache
def get_transcription() -> TranscriptionProvider:
    return build_transcription(get_settings())
