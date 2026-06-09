from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models import AuditAction, LeaveRequest, LeaveStatus, LeaveType, User
from app.schemas.common import LeaveRequestCreate, LeaveRequestOut, LeaveRequestUpdate, PaginatedResponse
from app.services.audit_service import log_audit
from app.services.serializers import model_to_dict

router = APIRouter(prefix="/api/leave-requests", tags=["leave"])

LEAVE_FIELDS = [
    "id", "employee_id", "leave_type", "start_date", "end_date",
    "reason", "status", "reviewed_by", "reviewed_at", "created_at", "updated_at",
]


@router.get("", response_model=PaginatedResponse[LeaveRequestOut])
async def list_leave_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-leave-requests", "approve-leave"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    query = select(LeaveRequest)
    if status_filter:
        query = query.where(LeaveRequest.status == LeaveStatus(status_filter))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(LeaveRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/{leave_id}", response_model=LeaveRequestOut)
async def get_leave_request(
    leave_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-leave-requests", "approve-leave"))],
):
    leave = await db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return leave


@router.post("", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    payload: LeaveRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("create-leave-request"))],
):
    data = payload.model_dump()
    data["leave_type"] = LeaveType(data["leave_type"])
    if hasattr(data["start_date"], "date"):
        data["start_date"] = data["start_date"].date()
    if hasattr(data["end_date"], "date"):
        data["end_date"] = data["end_date"].date()
    leave = LeaveRequest(**data)
    db.add(leave)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.CREATE,
        module="leave_requests",
        entity_id=leave.id,
        old_value=None,
        new_value=model_to_dict(leave, LEAVE_FIELDS),
    )
    await db.commit()
    await db.refresh(leave)
    return leave


@router.put("/{leave_id}", response_model=LeaveRequestOut)
async def update_leave_request(
    leave_id: str,
    payload: LeaveRequestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("view-leave-requests"))],
):
    leave = await db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    old_value = model_to_dict(leave, LEAVE_FIELDS)
    updates = payload.model_dump(exclude_unset=True)
    if "leave_type" in updates:
        updates["leave_type"] = LeaveType(updates["leave_type"])
    if updates.get("start_date") and hasattr(updates["start_date"], "date"):
        updates["start_date"] = updates["start_date"].date()
    if updates.get("end_date") and hasattr(updates["end_date"], "date"):
        updates["end_date"] = updates["end_date"].date()
    for key, value in updates.items():
        setattr(leave, key, value)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="leave_requests",
        entity_id=leave.id,
        old_value=old_value,
        new_value=model_to_dict(leave, LEAVE_FIELDS),
    )
    await db.commit()
    await db.refresh(leave)
    return leave


async def _review_leave(
    leave_id: str,
    new_status: LeaveStatus,
    db: AsyncSession,
    current_user: User,
) -> LeaveRequest:
    leave = await db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Leave request already reviewed")
    old_value = model_to_dict(leave, LEAVE_FIELDS)
    leave.status = new_status
    leave.reviewed_by = current_user.id
    leave.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="leave_requests",
        entity_id=leave.id,
        old_value=old_value,
        new_value=model_to_dict(leave, LEAVE_FIELDS),
    )
    await db.commit()
    await db.refresh(leave)
    return leave


@router.post("/{leave_id}/approve", response_model=LeaveRequestOut)
async def approve_leave(
    leave_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("approve-leave"))],
):
    return await _review_leave(leave_id, LeaveStatus.APPROVED, db, current_user)


@router.post("/{leave_id}/reject", response_model=LeaveRequestOut)
async def reject_leave(
    leave_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("approve-leave"))],
):
    return await _review_leave(leave_id, LeaveStatus.REJECTED, db, current_user)
