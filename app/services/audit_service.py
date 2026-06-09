from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_request_ip, get_request_user_agent
from app.models import AuditAction, AuditLog


async def log_audit(
    db: AsyncSession,
    *,
    user_id: str | None,
    action: AuditAction,
    module: str,
    entity_id: str | None,
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        module=module,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=get_request_ip(),
        user_agent=get_request_user_agent(),
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    await db.flush()
    return entry
