# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# Whisper weights for local transcription, fetched once at build so the container never needs
# the network at runtime. Override the size with --build-arg WHISPER_MODEL=small.en.
FROM build AS models
ARG WHISPER_MODEL=base.en
RUN /app/.venv/bin/python -c "from faster_whisper import download_model; \
    download_model('${WHISPER_MODEL}', cache_dir='/models')"

FROM python:3.12-slim-bookworm AS runtime
ARG WHISPER_MODEL=base.en
# ffmpeg/ffprobe: duration checks and decoding for local transcription.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /data/audio && chown app:app /data/audio
COPY --from=models --chown=app:app /models /models
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src ./src
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app evals/reports ./evals/reports
COPY --chown=app:app docker-entrypoint.sh ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 CARENOTE_AUDIO_DIR=/data/audio \
    CARENOTE_LOCAL_WHISPER_DIR=/models CARENOTE_LOCAL_WHISPER_MODEL=${WHISPER_MODEL} HF_HUB_OFFLINE=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "carenote.main:app", "--host", "0.0.0.0", "--port", "8000"]
