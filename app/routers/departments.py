from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.db.session import get_db
from app.models import AuditAction, Department, User
from app.schemas.common import DepartmentCreate, DepartmentOut, DepartmentUpdate, PaginatedResponse
from app.services.audit_service import log_audit
from app.services.serializers import model_to_dict

router = APIRouter(prefix="/api/departments", tags=["departments"])

DEPARTMENT_FIELDS = ["id", "name", "code", "description", "is_active", "sort_order", "created_at", "updated_at"]


@router.get("", response_model=PaginatedResponse[DepartmentOut])
async def list_departments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-departments"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    query = select(Department)
    if search:
        query = query.where(Department.name.ilike(f"%{search}%"))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Department.sort_order, Department.name).offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department(
    department_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-departments"))],
):
    dept = await db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("create-department"))],
):
    dept = Department(**payload.model_dump())
    db.add(dept)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.CREATE,
        module="departments",
        entity_id=dept.id,
        old_value=None,
        new_value=model_to_dict(dept, DEPARTMENT_FIELDS),
    )
    await db.commit()
    await db.refresh(dept)
    return dept


@router.put("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("update-department"))],
):
    dept = await db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    old_value = model_to_dict(dept, DEPARTMENT_FIELDS)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dept, key, value)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="departments",
        entity_id=dept.id,
        old_value=old_value,
        new_value=model_to_dict(dept, DEPARTMENT_FIELDS),
    )
    await db.commit()
    await db.refresh(dept)
    return dept


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("delete-department"))],
):
    dept = await db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    old_value = model_to_dict(dept, DEPARTMENT_FIELDS)
    await db.delete(dept)
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.DELETE,
        module="departments",
        entity_id=department_id,
        old_value=old_value,
        new_value=None,
    )
    await db.commit()
