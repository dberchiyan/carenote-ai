import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    at: dt.datetime
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
