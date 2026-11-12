"""Writing audit events. Callers commit together with the change they audit."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from carenote.audit.models import AuditEvent


def record(
    session: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
    )
    session.add(event)
    return event
