"""Health endpoints. These are the only routes (besides login) that do not require auth."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from carenote.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get("/live")
def live() -> LiveResponse:
    """Process is up."""
    return LiveResponse(status="ok")


@router.get("/ready", responses={503: {"model": ReadyResponse}})
def ready(response: Response, session: Annotated[Session, Depends(get_session)]) -> ReadyResponse:
    """Process is up and the database answers."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="unavailable", database="unavailable")
    return ReadyResponse(status="ok", database="ok")
