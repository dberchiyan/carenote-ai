from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from carenote.audit import service as audit
from carenote.audit.models import AuditEvent
from carenote.audit.schemas import AuditEventOut
from carenote.auth.deps import DbSession, current_user, require_roles
from carenote.auth.models import Role, User
from carenote.pagination import Page, PageParams, count, page, page_params

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(current_user)])

Auditor = Annotated[User, Depends(require_roles(Role.AUDITOR))]


@router.get("/actions")
def list_audit_actions(session: DbSession, _: Auditor) -> list[str]:
    """Every action name that has been recorded, for the log's filter. Not audited itself."""
    return list(session.scalars(select(AuditEvent.action).distinct().order_by(AuditEvent.action)))


@router.get("")
def list_audit_events(
    session: DbSession,
    user: Auditor,
    paging: Annotated[PageParams, Depends(page_params(default_limit=100, max_limit=500))],
    entity: Annotated[str | None, Query(max_length=32)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[AuditEventOut]:
    """Audit log, newest first. Auditor only; viewing it is itself audited."""
    query = select(AuditEvent, User.display_name).outerjoin(User, User.id == AuditEvent.actor_id)
    if entity:
        query = query.where(AuditEvent.entity == entity)
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if action:
        query = query.where(AuditEvent.action == action)
    total = count(session, query)
    rows = session.execute(
        query.order_by(AuditEvent.at.desc()).limit(paging.limit).offset(paging.offset)
    ).all()
    # Viewing is audited once per distinct view: the page polls, and a log of "looked at the
    # log" every few seconds would bury the events that matter.
    view = {"entity": entity, "entity_id": entity_id, "action": action, "offset": paging.offset}
    previous = session.scalar(
        select(AuditEvent.after)
        .where(AuditEvent.actor_id == user.id, AuditEvent.action == "audit.view")
        .order_by(AuditEvent.at.desc())
        .limit(1)
    )
    if previous != view:
        audit.record(session, actor_id=user.id, action="audit.view", entity="audit", after=view)
        session.commit()
    return page(
        [
            AuditEventOut(
                id=e.id,
                at=e.at,
                actor_id=e.actor_id,
                actor_name=name,
                action=e.action,
                entity=e.entity,
                entity_id=e.entity_id,
                before=e.before,
                after=e.after,
            )
            for e, name in rows
        ],
        total,
        paging,
    )
