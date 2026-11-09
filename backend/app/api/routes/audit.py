"""Authenticated audit-log read route."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.dispute import AuditLogPage
from app.services.audit_service import list_events

router = APIRouter()


@router.get("/audit-logs", response_model=AuditLogPage)
async def audit_logs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    entity_type: str | None = None, entity_id: UUID | None = None, action: str | None = None,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items, total = await list_events(
        db, current_user, page=page, page_size=page_size,
        entity_type=entity_type, entity_id=entity_id, action=action,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
