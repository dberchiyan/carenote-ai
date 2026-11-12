"""Application settings. All secrets come from the environment (or a local .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-only-insecure-session-secret"  # noqa: S105 - placeholder, rejected in prod


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CARENOTE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `cp .env.example .env` leaves keys empty: treat "" as unset, not as an empty secret.
        env_ignore_empty=True,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    # "json": one object per line with request_id / note_id, for log search. "text" for a terminal.
    log_format: Literal["text", "json"] = "text"

    # Runtime connection as the restricted app role (no UPDATE/DELETE on audit_events).
    database_url: str = "postgresql+psycopg://carenote_app:carenote_app@localhost:5432/carenote"
    # Migrations run as the schema owner. Falls back to database_url when unset.
    migration_database_url: str | None = None
    fhir_base_url: str = "http://localhost:8090/fhir"

    session_secret: SecretStr = SecretStr(DEV_SESSION_SECRET)
    session_max_age_s: int = 12 * 60 * 60
    # Demo logins allowed per minute from one client address. A classroom behind NAT or a CI
    # runner shares one address, so this is well above any honest rate, not just above a user's.
    login_rate_limit_per_minute: int = 60

    # Browser origins allowed to call the API directly (the web app normally proxies instead).
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Provider selection. "local" transcribes on this machine with Whisper (no key, nothing
    # leaves the host); "fake" never looks at the audio and is for tests only.
    transcription_provider: Literal["local", "fake", "openai"] = "local"
    llm_provider: Literal["fake", "anthropic", "openai"] = "fake"
    local_whisper_model: str = "base.en"
    # Where the Whisper weights live (downloaded at image build; ~150 MB for base.en).
    local_whisper_dir: Path | None = None

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high"] = "medium"
    openai_model: str = "gpt-5-mini"
    openai_transcription_model: str = "gpt-4o-transcribe"

    # Uploaded audio lives here (a Docker volume in compose).
    audio_dir: Path = Path("data/audio")
    max_upload_bytes: int = 10 * 1024 * 1024
    max_audio_seconds: float = 120.0
    # A note still processing after this long is considered stalled (the worker died) and
    # may be retried from its last good step.
    processing_timeout_s: int = 180
    # Budget for one note's background processing; past it the note fails (retryable) instead
    # of holding a worker. Provider calls are bounded below so the budget is enforceable.
    pipeline_deadline_s: int = 120
    provider_timeout_s: int = 45
    provider_max_retries: int = 1

    # Offline eval reports shown on the AI quality page (copied into the image at build time).
    eval_reports_dir: Path = Path(__file__).resolve().parents[2] / "evals" / "reports"

    @model_validator(mode="after")
    def _reject_dev_secret_in_prod(self) -> "Settings":
        if self.env == "prod" and self.session_secret.get_secret_value() == DEV_SESSION_SECRET:
            raise ValueError("CARENOTE_SESSION_SECRET must be set in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
