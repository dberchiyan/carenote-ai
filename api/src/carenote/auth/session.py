"""Signed, httpOnly session cookie carrying the user id."""

import uuid

from itsdangerous import BadSignature, URLSafeTimedSerializer

from carenote.config import Settings

COOKIE_NAME = "carenote_session"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret.get_secret_value(), salt="session")


def sign(user_id: uuid.UUID, settings: Settings) -> str:
    return _serializer(settings).dumps(str(user_id))


def unsign(token: str, settings: Settings) -> uuid.UUID | None:
    try:
        value = _serializer(settings).loads(token, max_age=settings.session_max_age_s)
        return uuid.UUID(str(value))
    except (BadSignature, ValueError):
        return None
