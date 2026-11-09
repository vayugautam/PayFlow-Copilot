"""Append-only audit event persistence."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def record_event(db: AsyncSession, actor: User | None, *, action: str, entity_type: str,
                       entity_id: UUID, details: dict | None = None,
                       ip_address: str | None = None, user_agent: str | None = None) -> AuditLog:
    event = AuditLog(
        actor_user_id=actor.id if actor else None, action=action, entity_type=entity_type,
        entity_id=entity_id, details=details, ip_address=ip_address, user_agent=user_agent,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def list_events(db: AsyncSession, user: User, *, page: int, page_size: int,
                      entity_type: str | None = None, entity_id: UUID | None = None,
                      action: str | None = None) -> tuple[list[AuditLog], int]:
    filters = [AuditLog.actor_user_id == user.id]
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id:
        filters.append(AuditLog.entity_id == entity_id)
    if action:
        filters.append(AuditLog.action == action)
    total = int(await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0)
    result = await db.scalars(
        select(AuditLog).where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return list(result), total
