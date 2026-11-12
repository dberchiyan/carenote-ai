"""Demo login: pick one of the seeded demo users. No passwords — this is a demo."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select

from carenote.audit import service as audit
from carenote.auth.deps import CurrentUser, DbSession
from carenote.auth.models import User
from carenote.auth.schemas import DemoLoginIn, UserOut
from carenote.auth.session import COOKIE_NAME, sign
from carenote.config import Settings, get_settings
from carenote.errors import unauthenticated
from carenote.ratelimit import LOGIN_WINDOW, limit

router = APIRouter(prefix="/auth", tags=["auth"])

# Users offered on the login screen, in display order.
DEMO_LOGIN_USERNAMES = ("nurse", "charge", "auditor")


@router.get("/demo-users")
def demo_users(session: DbSession) -> list[UserOut]:
    """Public: the login screen lists these as one-click cards."""
    users = session.scalars(select(User).where(User.username.in_(DEMO_LOGIN_USERNAMES))).all()
    by_name = {u.username: u for u in users}
    return [UserOut.model_validate(by_name[n]) for n in DEMO_LOGIN_USERNAMES if n in by_name]


@router.post("/demo-login", dependencies=[Depends(limit(LOGIN_WINDOW))])
def demo_login(
    body: DemoLoginIn,
    response: Response,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserOut:
    user = session.scalar(select(User).where(User.username == body.username))
    if user is None:
        raise unauthenticated("Unknown demo user")
    response.set_cookie(
        COOKIE_NAME,
        sign(user.id, settings),
        max_age=settings.session_max_age_s,
        httponly=True,
        samesite="lax",
        secure=settings.env == "prod",
    )
    audit.record(session, actor_id=user.id, action="auth.login", entity="user", entity_id=user.id)
    session.commit()
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, user: CurrentUser, session: DbSession) -> None:
    response.delete_cookie(COOKIE_NAME)
    audit.record(session, actor_id=user.id, action="auth.logout", entity="user", entity_id=user.id)
    session.commit()


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
