from datetime import datetime
from typing import Generic, List, Optional, TypeVar

import email_validator
# Allow .local domain for local dev environment email validation
if isinstance(email_validator.SPECIAL_USE_DOMAIN_NAMES, list) and "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("local")
elif isinstance(email_validator.SPECIAL_USE_DOMAIN_NAMES, set) and "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.discard("local")

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class EncryptedEnvelope(BaseModel):
    iv: str
    ciphertext: str
    tag: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    is_super_admin: bool
    permissions: List[PermissionOut] = []


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_active: bool
    role: RoleOut


class AuthMeResponse(BaseModel):
    user: UserOut
    permissions: List[str]
    is_super_admin: bool


class SubModulePageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    route_path: str
    permission_names: List[str]
    sort_order: int


class SubModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    sort_order: int
    pages: List[SubModulePageOut]


class MasterModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    sort_order: int
    sub_modules: List[SubModuleOut]


class DepartmentBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class DepartmentOut(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class EmployeeBase(BaseModel):
    department_id: Optional[str] = None
    employee_code: str
    email: EmailStr
    full_name: str
    job_title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = None
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    department_id: Optional[str] = None
    employee_code: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    department_id: Optional[str] = None
    employee_code: str
    email: str
    full_name: str
    job_title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LeaveRequestCreate(BaseModel):
    employee_id: str
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None


class LeaveRequestUpdate(BaseModel):
    leave_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    reason: Optional[str] = None


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_id: str
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_super_admin: bool = False


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_super_admin: Optional[bool] = None


class RolePermissionsUpdate(BaseModel):
    permission_ids: List[str] = Field(default_factory=list)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str] = None
    action: str
    module: str
    entity_id: Optional[str] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
