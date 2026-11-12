"""Offset pagination for list endpoints: `{items, total, limit, offset}`.

Small on purpose. Lists here are bounded (one patient's observations, the audit log behind
filters), so a stable offset page with a total is what the UI needs; cursors would add
nothing but complexity.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def page_params(default_limit: int, max_limit: int) -> type[PageParams]:
    """A dependency with the bounds baked in, e.g. `Depends(page_params(100, 500))`."""

    class Params(PageParams):
        def __init__(
            self,
            limit: Annotated[int, Query(ge=1, le=max_limit)] = default_limit,
            offset: Annotated[int, Query(ge=0)] = 0,
        ) -> None:
            object.__setattr__(self, "limit", limit)
            object.__setattr__(self, "offset", offset)

    return Params


def count(session: Session, query: Select[*tuple[Any, ...]]) -> int:
    """Rows the unpaged query would return."""
    return session.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0


def page[T](items: Sequence[T], total: int, params: PageParams) -> Page[T]:
    return Page(items=list(items), total=total, limit=params.limit, offset=params.offset)
