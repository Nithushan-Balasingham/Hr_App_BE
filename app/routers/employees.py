from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models import AuditAction, Employee, User
from app.schemas.common import EmployeeCreate, EmployeeOut, EmployeeUpdate, PaginatedResponse
from app.services.audit_service import log_audit
from app.services.serializers import model_to_dict

router = APIRouter(prefix="/api/employees", tags=["employees"])

EMPLOYEE_FIELDS = [
    "id", "department_id", "employee_code", "email", "full_name",
    "job_title", "phone", "hire_date", "is_active", "created_at", "updated_at",
]


@router.get("", response_model=PaginatedResponse[EmployeeOut])
async def list_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-employees"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    query = select(Employee)
    if search:
        query = query.where(Employee.full_name.ilike(f"%{search}%"))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Employee.full_name).offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("view-employees"))],
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("create-employee"))],
):
    data = payload.model_dump()
    if data.get("hire_date") and hasattr(data["hire_date"], "date"):
        data["hire_date"] = data["hire_date"].date()
    employee = Employee(**data)
    db.add(employee)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.CREATE,
        module="employees",
        entity_id=employee.id,
        old_value=None,
        new_value=model_to_dict(employee, EMPLOYEE_FIELDS),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("update-employee"))],
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    old_value = model_to_dict(employee, EMPLOYEE_FIELDS)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("hire_date") and hasattr(updates["hire_date"], "date"):
        updates["hire_date"] = updates["hire_date"].date()
    for key, value in updates.items():
        setattr(employee, key, value)
    await db.flush()
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.UPDATE,
        module="employees",
        entity_id=employee.id,
        old_value=old_value,
        new_value=model_to_dict(employee, EMPLOYEE_FIELDS),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("delete-employee"))],
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    old_value = model_to_dict(employee, EMPLOYEE_FIELDS)
    await db.delete(employee)
    await log_audit(
        db,
        user_id=current_user.id,
        action=AuditAction.DELETE,
        module="employees",
        entity_id=employee_id,
        old_value=old_value,
        new_value=None,
    )
    await db.commit()
