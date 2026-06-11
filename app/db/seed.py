import asyncio
from datetime import date

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Department,
    Employee,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    MasterModule,
    Permission,
    Role,
    SubModule,
    SubModulePage,
    User,
    role_permissions,
)
# Add this patch right under your imports at the top of app/db/seed.py
from sqlalchemy.dialects.mysql.aiomysql import AsyncAdapt_aiomysql_connection

original_ping = AsyncAdapt_aiomysql_connection.ping


def patched_ping(self, reconnect=True):  # Makes the argument optional
    return original_ping(self, reconnect)


AsyncAdapt_aiomysql_connection.ping = patched_ping
# -------------------------
# NAVIGATION STRUCTURE
# -------------------------
NAV_TREE = [
    {
        "name": "Dashboard",
        "slug": "dashboard",
        "sort_order": 1,
        "sub_modules": [
            {
                "name": "Overview",
                "slug": "overview",
                "sort_order": 1,
                "pages": [
                    {
                        "name": "Dashboard Home",
                        "slug": "dashboard-home",
                        "route_path": "/hr/dashboard",
                        "permission_names": [],
                        "sort_order": 1,
                    }
                ],
            }
        ],
    },
    {
        "name": "Employee Management",
        "slug": "employee-management",
        "sort_order": 2,
        "sub_modules": [
            {
                "name": "Employees",
                "slug": "employees",
                "sort_order": 1,
                "pages": [
                    {"name": "All Employees", "slug": "all-employees", "route_path": "/hr/employees", "permission_names": ["view-employees"], "sort_order": 1},
                    {"name": "Create Employee", "slug": "create-employee", "route_path": "/hr/employees/create", "permission_names": ["create-employee"], "sort_order": 2},
                    {"name": "Edit Employee", "slug": "edit-employee", "route_path": "/hr/employees/:id/edit", "permission_names": ["update-employee"], "sort_order": 3},
                ],
            },
            {
                "name": "Departments",
                "slug": "departments",
                "sort_order": 2,
                "pages": [
                    {"name": "All Departments", "slug": "all-departments", "route_path": "/hr/departments", "permission_names": ["view-departments"], "sort_order": 1},
                    {"name": "Create Department", "slug": "create-department", "route_path": "/hr/departments/create", "permission_names": ["create-department"], "sort_order": 2},
                ],
            },
        ],
    },
    {
        "name": "Leave Management",
        "slug": "leave-management",
        "sort_order": 3,
        "sub_modules": [
            {
                "name": "Leave Requests",
                "slug": "leave-requests",
                "sort_order": 1,
                "pages": [
                    {"name": "All Leave Requests", "slug": "all-leave-requests", "route_path": "/hr/leave/requests", "permission_names": ["view-leave-requests"], "sort_order": 1},
                    {"name": "Approve Leave", "slug": "approve-leave", "route_path": "/hr/leave/approve", "permission_names": ["approve-leave"], "sort_order": 2},
                ],
            },
        ],
    },
    {
        "name": "Administration",
        "slug": "administration",
        "sort_order": 4,
        "sub_modules": [
            {
                "name": "Roles & Permissions",
                "slug": "roles-permissions",
                "sort_order": 1,
                "pages": [
                    {"name": "All Roles", "slug": "all-roles", "route_path": "/hr/admin/roles", "permission_names": ["view-roles"], "sort_order": 1},
                    {"name": "Create Role", "slug": "create-role", "route_path": "/hr/admin/roles/create", "permission_names": ["create-role"], "sort_order": 2},
                ],
            },
            {
                "name": "Audit Logs",
                "slug": "audit-logs",
                "sort_order": 2,
                "pages": [
                    {"name": "View Audit Logs", "slug": "view-audit-logs", "route_path": "/hr/admin/audit-logs", "permission_names": ["view-audit-logs"], "sort_order": 1},
                ],
            },
        ],
    },
]

EXTRA_PERMISSIONS = [
    # Employee extras (no dedicated nav page)
    ("delete-employee", "Delete Employee", "Permanently delete employee records"),
    # Department extras
    ("delete-department", "Delete Department", "Permanently delete departments"),
    ("update-department", "Update Department", "Edit department records"),
    # Role extras
    ("update-role", "Update Role", "Edit roles and assign permissions"),
    # Leave extras
    ("create-leave-request", "Create Leave Request", "Submit leave requests"),
]

ROLE_PERMISSIONS = {
    "HR Manager": [
        "view-employees", "create-employee", "update-employee", "delete-employee",
        "view-departments", "create-department", "update-department", "delete-department",
        "view-leave-requests", "approve-leave", "create-leave-request",
        "view-roles", "create-role", "update-role",
        "view-audit-logs",
    ],
    "Employee": [
        "view-leave-requests", "create-leave-request",
    ],
}


# -------------------------
# SEED FUNCTION
# -------------------------
async def seed() -> None:
    try:
        # Force SQLAlchemy to dynamically build tables if they don't exist yet
        print("Checking/Creating system schema tables...")
        from app.models import Base  # Or wherever your primary Declarative Base is initialized
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Schema sync verification complete.")

        # Execute data insertion pipelines
        await _run_seed()
    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        raise e
    finally:
        await engine.dispose()


async def _run_seed() -> None:
    async with AsyncSessionLocal() as db:

        existing = await db.scalar(select(MasterModule.id).limit(1))
        if existing:
            print("Database already seeded. Skipping.")
            return

        permission_map: dict[str, Permission] = {}

        # -------------------------
        # MODULE TREE
        # -------------------------
        for master_data in NAV_TREE:
            master = MasterModule(
            name=master_data["name"],
            slug=master_data["slug"],
            sort_order=master_data["sort_order"],
            )            
            db.add(master)
            await db.flush()

            for sub_data in master_data["sub_modules"]:
                sub = SubModule(
                    master_module_id=master.id,
                    name=sub_data["name"],
                    slug=sub_data["slug"],
                    sort_order=sub_data["sort_order"],
                    is_active=True,
                )
                db.add(sub)
                await db.flush()

                page_permission_slugs = set()

                for page_data in sub_data["pages"]:
                    db.add(SubModulePage(
                        sub_module_id=sub.id,
                        name=page_data["name"],
                        slug=page_data["slug"],
                        route_path=page_data["route_path"],
                        permission_names=page_data["permission_names"],
                        sort_order=page_data["sort_order"],
                        is_active=True,
                    ))
                    page_permission_slugs.update(page_data["permission_names"])

                for slug in page_permission_slugs:
                    if slug not in permission_map:
                        perm = Permission(
                            sub_module_id=sub.id,
                            name=slug.replace("-", " ").title(),
                            slug=slug,
                            description=f"Permission: {slug}",
                        )
                        db.add(perm)
                        await db.flush()
                        permission_map[slug] = perm

                for slug, name, desc in EXTRA_PERMISSIONS:
                    if slug in permission_map:
                        continue

                    sub_match = (
                        (sub.slug == "employees" and "employee" in slug)
                        or (sub.slug == "departments" and "department" in slug)
                        or (sub.slug == "roles-permissions" and "role" in slug)
                        or (sub.slug == "leave-requests" and "leave" in slug)
                    )
                    if sub_match:
                        perm = Permission(
                            sub_module_id=sub.id,
                            name=name,
                            slug=slug,
                            description=desc,
                        )
                        db.add(perm)
                        await db.flush()
                        permission_map[slug] = perm

        # -------------------------
        # ROLES
        # -------------------------
        super_admin = Role(name="Super Admin", description="Full system access", is_super_admin=True)
        hr_manager = Role(name="HR Manager", description="HR operations manager")
        employee_role = Role(name="Employee", description="Standard employee")

        db.add_all([super_admin, hr_manager, employee_role])
        await db.flush()

        # -------------------------
        # ROLE PERMISSIONS
        # -------------------------
        role_permission_rows = []

        role_objects = {
            "HR Manager": hr_manager,
            "Employee": employee_role,
        }

        for role_name, perm_slugs in ROLE_PERMISSIONS.items():
            role_obj = role_objects.get(role_name)
            if not role_obj:
                continue

            for slug in perm_slugs:
                perm = permission_map.get(slug)
                if perm:
                    role_permission_rows.append({
                        "role_id": role_obj.id,
                        "permission_id": perm.id,
                    })

        if role_permission_rows:
            await db.execute(role_permissions.insert(), role_permission_rows)

        # -------------------------
        # USERS
        # -------------------------
        admin_user = User(
            role_id=super_admin.id,
            email="admin@hrportal.local",
            hashed_password=hash_password("Admin@123"),
            full_name="Super Admin",
            is_active=True,
        )
        manager_user = User(
            role_id=hr_manager.id,
            email="hr.manager@hrportal.local",
            hashed_password=hash_password("HrManager@123"),
            full_name="HR Manager",
            is_active=True,
        )
        emp_user = User(
            role_id=employee_role.id,
            email="employee@hrportal.local",
            hashed_password=hash_password("Employee@123"),
            full_name="Jane Employee",
            is_active=True,
        )
        db.add_all([admin_user, manager_user, emp_user])
        await db.flush()

        # -------------------------
        # DEPARTMENTS
        # -------------------------
        dept_hr = Department(name="Human Resources", code="HR", description="HR department", sort_order=1)
        dept_eng = Department(name="Engineering", code="ENG", description="Engineering department", sort_order=2)

        db.add_all([dept_hr, dept_eng])
        await db.flush()

        # -------------------------
        # EMPLOYEES
        # -------------------------
        emp1 = Employee(
            department_id=dept_eng.id,
            employee_code="EMP001",
            email="john.doe@company.local",
            full_name="John Doe",
            job_title="Software Engineer",
            phone="+1-555-0101",
            hire_date=date(2023, 1, 15),
            is_active=True,
        )

        emp2 = Employee(
            department_id=dept_hr.id,
            employee_code="EMP002",
            email="sarah.smith@company.local",
            full_name="Sarah Smith",
            job_title="HR Specialist",
            phone="+1-555-0102",
            hire_date=date(2022, 6, 1),
            is_active=True,
        )

        db.add_all([emp1, emp2])
        await db.flush()

        # -------------------------
        # LEAVE REQUESTS
        # -------------------------
        db.add_all([
            LeaveRequest(
                employee_id=emp1.id,
                leave_type=LeaveType.ANNUAL,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 5),
                reason="Family vacation",
                status=LeaveStatus.PENDING,
            ),
            LeaveRequest(
                employee_id=emp2.id,
                leave_type=LeaveType.SICK,
                start_date=date(2026, 5, 10),
                end_date=date(2026, 5, 11),
                reason="Medical appointment",
                status=LeaveStatus.APPROVED,
                reviewed_by=manager_user.id,
            ),
        ])

        # -------------------------
        # FINAL COMMIT ONLY
        # -------------------------
        await db.commit()

        print("Seed completed successfully.")
        print("Super Admin: admin@hrportal.local / Admin@123")
        print("HR Manager: hr.manager@hrportal.local / HrManager@123")
        print("Employee: employee@hrportal.local / Employee@123")


if __name__ == "__main__":
    asyncio.run(seed())