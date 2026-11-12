"""Request IDs and structured logs.

Every request gets an `X-Request-ID` (the caller's, sanitised, or a fresh one) that is echoed
in the response and stamped on every log line written while handling it. Background
processing stamps the note id the same way, so one `note_id` filter in the log search tells
the whole story of a note: steps, model, tokens, cost, failure.
"""

import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Literal

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
note_id_var: ContextVar[str | None] = ContextVar("note_id", default=None)

log = logging.getLogger("carenote.http")


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def clean_request_id(value: str | None) -> str | None:
    """A caller-supplied id is kept only if it is short and plain; anything else is replaced."""
    if not value:
        return None
    cleaned = _SAFE_ID.sub("", value)[:64]
    return cleaned or None


@contextmanager
def bound_note(note_id: uuid.UUID | str) -> Iterator[None]:
    """Stamp `note_id` on every log line inside the block (background processing)."""
    token = note_id_var.set(str(note_id))
    try:
        yield
    finally:
        note_id_var.reset(token)


class RequestIdMiddleware:
    """Pure ASGI: set the request id, echo it, log one access line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = clean_request_id(headers.get(REQUEST_ID_HEADER)) or new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                raw = list(message.get("headers", []))
                raw.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = raw
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
            path = scope.get("path", "")
            if not path.startswith("/health"):
                log.info(
                    "%s %s -> %s",
                    scope.get("method"),
                    path,
                    status,
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000),
                        "request_id": request_id,
                    },
                )


class ContextFilter(logging.Filter):
    """Copy the request and note ids from context onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        if not hasattr(record, "note_id"):
            record.note_id = note_id_var.get()
        return True


_STANDARD_ATTRS = frozenset(
    {
        *vars(logging.LogRecord("", 0, "", 0, "", (), None)),
        "message",
        "asctime",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line: fixed fields first, then whatever was passed as `extra`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ids = " ".join(
            f"{k}={v}"
            for k, v in (
                ("req", getattr(record, "request_id", None)),
                ("note", getattr(record, "note_id", None)),
            )
            if v
        )
        base = super().format(record)
        return f"{base} [{ids}]" if ids else base


class _AppHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker type, so re-configuring (tests create the app repeatedly) replaces only ours."""


def configure_logging(level: str, fmt: Literal["text", "json"]) -> None:
    handler = _AppHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter() if fmt == "json" else TextFormatter("%(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    # Replace only our own handler (the app is created more than once in tests); leave
    # pytest's capture and anything else alone.
    for existing in [h for h in root.handlers if isinstance(h, _AppHandler)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
