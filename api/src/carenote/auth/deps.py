"""Authentication and authorization dependencies. Deny by default."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from carenote.auth.models import Role, User
from carenote.auth.session import COOKIE_NAME, unsign
from carenote.config import Settings, get_settings
from carenote.db import get_session
from carenote.errors import forbidden, unauthenticated

DbSession = Annotated[Session, Depends(get_session)]


def current_user(
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    user_id = unsign(token, settings) if token else None
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise unauthenticated()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise forbidden("Not allowed for your role", role=user.role.value)
        return user

    return dependency


def ensure_ward_access(user: User, ward: str) -> None:
    """Nurses and charge nurses see only their own ward; auditors read every ward."""
    if user.role is Role.AUDITOR:
        return
    if user.ward != ward:
        raise forbidden("Not allowed for this ward", ward=ward)
