"""One error contract for the whole API: `{code, message, details}`.

`code` is a closed enum the web app can branch on; `message` is for people; `details` carries
structured context (the note's status on a conflict, the invalid fields on a 422). Raise
`ApiError` from anywhere below the routers; `install` turns it (and FastAPI's own errors) into
the same JSON shape.
"""

import enum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(enum.StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    INVALID_STATE = "invalid_state"  # the note is not in a status that allows this action
    CONFLICT = "conflict"  # someone else changed the resource; reload
    PAYLOAD_REJECTED = "payload_rejected"  # the upload is not usable audio
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


class ErrorOut(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any]


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def to_out(self) -> ErrorOut:
        return ErrorOut(code=self.code, message=self.message, details=self.details)


# Shortcuts for the common refusals, so call sites read as intent.
def unauthenticated(message: str = "Not authenticated") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, message)


def forbidden(message: str, **details: Any) -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN, message, details)


def not_found(entity: str, **details: Any) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, f"{entity} not found", details)


def invalid_state(message: str, **details: Any) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, ErrorCode.INVALID_STATE, message, details)


def conflict(message: str, **details: Any) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, ErrorCode.CONFLICT, message, details)


def payload_rejected(message: str, **details: Any) -> ApiError:
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.PAYLOAD_REJECTED, message, details
    )


_BY_STATUS = {
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_422_UNPROCESSABLE_CONTENT: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}


def _respond(
    status_code: int, out: ErrorOut, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(out.model_dump(mode="json"), status_code=status_code, headers=headers)


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):  # pragma: no cover - registered for ApiError only
        raise exc
    return _respond(exc.status_code, exc.to_out())


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    """Starlette's own refusals (unknown path, wrong method, 405) in the same shape."""
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    code = _BY_STATUS.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    headers = dict(exc.headers) if exc.headers else None
    return _respond(exc.status_code, ErrorOut(code=code, message=message, details={}), headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    fields = [
        {
            "path": ".".join(str(p) for p in e["loc"]),
            "message": e["msg"].removeprefix("Value error, "),
            "type": e["type"],
        }
        for e in exc.errors()
    ]
    return _respond(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorOut(
            code=ErrorCode.VALIDATION_ERROR,
            message="The request was not valid.",
            details={"fields": fields},
        ),
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)


def document(schema: dict[str, Any]) -> dict[str, Any]:
    """Make the error shape part of the published contract: an `ErrorOut` component and a
    `default` response on every operation, so the generated web client knows the type."""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["ErrorCode"] = {
        "title": "ErrorCode",
        "type": "string",
        "enum": [c.value for c in ErrorCode],
    }
    components["ErrorOut"] = {
        "title": "ErrorOut",
        "type": "object",
        "required": ["code", "message", "details"],
        "properties": {
            "code": {"$ref": "#/components/schemas/ErrorCode"},
            "message": {"type": "string", "title": "Message"},
            "details": {"type": "object", "title": "Details", "additionalProperties": True},
        },
    }
    error_response = {
        "description": "Error",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorOut"}}},
    }
    for operations in schema["paths"].values():
        for op in operations.values():
            responses = op.setdefault("responses", {})
            # FastAPI's stock 422 entry points at its own HTTPValidationError; ours replaces it.
            responses.pop("422", None)
            responses["default"] = error_response
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    return schema
