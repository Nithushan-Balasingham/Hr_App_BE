from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models import AuditAction, Permission, Role, User
from app.schemas.common import PaginatedResponse, RoleCreate, RoleOut, RolePermissionsUpdate, RoleUpdate
from app.services.audit_service import log_audit
from app.services.serializers import model_to_dict

router = APIRouter(prefix="/api/roles", tags=["roles"])

ROLE_FIELDS = ["id", "name", "description", "is_super_admin", "created_at", "updated_at"]


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_super_admin=role.is_super_admin,
        permissions=[
            {"id": p.id, "name": p.name, "slug": p.slug, "description": p.description}
            for p in role.permissions
        ],
    )


@router.get("", response_model=PaginatedResponse[RoleOut])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-roles"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    query = select(Role).options(selectinload(Role.permissions))
    if search:
        query = query.where(Role.name.ilike(f"%{search}%"))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(Role.name).offset((page - 1) * page_size).limit(page_size))
    items = [_serialize_role(r) for r in result.scalars().unique().all()]
    return PaginatedResponse(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-roles"))],
):
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return _serialize_role(role)


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("create-role"))],
):
    role = Role(**payload.model_dump())
    db.add(role)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.CREATE,
        module="roles",
        entity_id=role.id,
        old_value=None,
        new_value=model_to_dict(role, ROLE_FIELDS),
    )
    await db.commit()
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id))
    return _serialize_role(result.scalar_one())


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("update-role"))],
):
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    old_value = model_to_dict(role, ROLE_FIELDS)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="roles",
        entity_id=role.id,
        old_value=old_value,
        new_value=model_to_dict(role, ROLE_FIELDS),
    )
    await db.commit()
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id))
    return _serialize_role(result.scalar_one())


@router.put("/{role_id}/permissions", response_model=RoleOut)
async def update_role_permissions(
    role_id: str,
    payload: RolePermissionsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("update-role"))],
):
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    old_value = {"permission_ids": [p.id for p in role.permissions]}
    perm_result = await db.execute(select(Permission).where(Permission.id.in_(payload.permission_ids)))
    role.permissions = list(perm_result.scalars().all())
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="roles",
        entity_id=role.id,
        old_value=old_value,
        new_value={"permission_ids": [p.id for p in role.permissions]},
    )
    await db.commit()
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id))
    return _serialize_role(result.scalar_one())
