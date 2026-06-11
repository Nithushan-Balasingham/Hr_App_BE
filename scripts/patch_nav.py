"""
patch_nav.py – One-shot script to add missing nav modules + permissions to
an already-seeded database.

Run from the HR_BE directory:
    python -m scripts.patch_nav

What it does:
  1. Inserts Leave Management → Leave Requests sub-module + pages
  2. Inserts Administration → Roles & Permissions sub-module + pages
  3. Inserts Administration → Audit Logs sub-module + page
  4. Creates any permissions that don't already exist
  5. Links new permissions to HR Manager and Employee roles
"""

import asyncio

from sqlalchemy import select, insert

from app.db.session import AsyncSessionLocal, engine
from app.models import (
    MasterModule,
    SubModule,
    SubModulePage,
    Permission,
    Role,
    role_permissions,
)

# ---------------------------------------------------------------------------
# Data to patch in
# ---------------------------------------------------------------------------

PATCH_TREE = [
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
                    {
                        "name": "All Leave Requests",
                        "slug": "all-leave-requests",
                        "route_path": "/hr/leave/requests",
                        "permission_names": ["view-leave-requests"],
                        "sort_order": 1,
                    },
                    {
                        "name": "Approve Leave",
                        "slug": "approve-leave",
                        "route_path": "/hr/leave/approve",
                        "permission_names": ["approve-leave"],
                        "sort_order": 2,
                    },
                ],
            }
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
                    {
                        "name": "All Roles",
                        "slug": "all-roles",
                        "route_path": "/hr/admin/roles",
                        "permission_names": ["view-roles"],
                        "sort_order": 1,
                    },
                    {
                        "name": "Create Role",
                        "slug": "create-role",
                        "route_path": "/hr/admin/roles/create",
                        "permission_names": ["create-role"],
                        "sort_order": 2,
                    },
                ],
            },
            {
                "name": "Audit Logs",
                "slug": "audit-logs",
                "sort_order": 2,
                "pages": [
                    {
                        "name": "View Audit Logs",
                        "slug": "view-audit-logs",
                        "route_path": "/hr/admin/audit-logs",
                        "permission_names": ["view-audit-logs"],
                        "sort_order": 1,
                    }
                ],
            },
        ],
    },
]

# Permissions that have no nav page but should exist
EXTRA_PERMISSIONS = [
    ("update-role", "Update Role", "Edit roles and assign permissions"),
    ("create-leave-request", "Create Leave Request", "Submit leave requests"),
]

# Role → permission slug mapping for new permissions only
ROLE_PERMISSIONS_PATCH = {
    "HR Manager": [
        "view-leave-requests",
        "approve-leave",
        "view-roles",
        "create-role",
        "update-role",
        "view-audit-logs",
        "create-leave-request",
    ],
    "Employee": [
        "view-leave-requests",
        "create-leave-request",
    ],
}


# ---------------------------------------------------------------------------
# Patch logic
# ---------------------------------------------------------------------------

async def patch() -> None:
    try:
        await _run_patch()
    finally:
        await engine.dispose()


async def _run_patch() -> None:
    async with AsyncSessionLocal() as db:
        # ---- build existing permission map ----
        existing_perms_result = await db.execute(select(Permission))
        permission_map: dict[str, Permission] = {
            p.slug: p for p in existing_perms_result.scalars().all()
        }
        print(f"Found {len(permission_map)} existing permissions.")

        # ---- build existing master-module slugs ----
        existing_masters_result = await db.execute(select(MasterModule))
        existing_master_slugs = {m.slug: m for m in existing_masters_result.scalars().all()}

        # ---- insert missing master modules + sub-modules + pages ----
        for master_data in PATCH_TREE:
            slug = master_data["slug"]
            if slug in existing_master_slugs:
                master = existing_master_slugs[slug]
                print(f"Master module '{slug}' already exists — checking sub-modules.")
            else:
                master = MasterModule(
                    name=master_data["name"],
                    slug=slug,
                    sort_order=master_data["sort_order"],
                )
                db.add(master)
                await db.flush()
                print(f"  ✔ Created master module: {slug}")

            # existing sub-module slugs under this master
            existing_subs_result = await db.execute(
                select(SubModule).where(SubModule.master_module_id == master.id)
            )
            existing_sub_slugs = {s.slug: s for s in existing_subs_result.scalars().all()}

            for sub_data in master_data["sub_modules"]:
                sub_slug = sub_data["slug"]
                if sub_slug in existing_sub_slugs:
                    sub = existing_sub_slugs[sub_slug]
                    print(f"    Sub-module '{sub_slug}' already exists — checking pages.")
                else:
                    sub = SubModule(
                        master_module_id=master.id,
                        name=sub_data["name"],
                        slug=sub_slug,
                        sort_order=sub_data["sort_order"],
                        is_active=True,
                    )
                    db.add(sub)
                    await db.flush()
                    print(f"    ✔ Created sub-module: {sub_slug}")

                # existing page slugs under this sub-module
                existing_pages_result = await db.execute(
                    select(SubModulePage).where(SubModulePage.sub_module_id == sub.id)
                )
                existing_page_slugs = {p.slug for p in existing_pages_result.scalars().all()}

                for page_data in sub_data["pages"]:
                    page_slug = page_data["slug"]
                    if page_slug in existing_page_slugs:
                        print(f"      Page '{page_slug}' already exists. Skipping.")
                        continue

                    db.add(SubModulePage(
                        sub_module_id=sub.id,
                        name=page_data["name"],
                        slug=page_slug,
                        route_path=page_data["route_path"],
                        permission_names=page_data["permission_names"],
                        sort_order=page_data["sort_order"],
                        is_active=True,
                    ))
                    print(f"      ✔ Created page: {page_slug}")

                    # create permissions for this page
                    for perm_slug in page_data["permission_names"]:
                        if perm_slug not in permission_map:
                            perm = Permission(
                                sub_module_id=sub.id,
                                name=perm_slug.replace("-", " ").title(),
                                slug=perm_slug,
                                description=f"Permission: {perm_slug}",
                            )
                            db.add(perm)
                            await db.flush()
                            permission_map[perm_slug] = perm
                            print(f"        ✔ Created permission: {perm_slug}")
                        else:
                            print(f"        Permission '{perm_slug}' already exists.")

                # create extra permissions attached to this sub-module
                for perm_slug, perm_name, perm_desc in EXTRA_PERMISSIONS:
                    if perm_slug in permission_map:
                        continue
                    sub_match = (
                        (sub_slug == "roles-permissions" and "role" in perm_slug)
                        or (sub_slug == "leave-requests" and "leave" in perm_slug)
                    )
                    if sub_match:
                        perm = Permission(
                            sub_module_id=sub.id,
                            name=perm_name,
                            slug=perm_slug,
                            description=perm_desc,
                        )
                        db.add(perm)
                        await db.flush()
                        permission_map[perm_slug] = perm
                        print(f"      ✔ Created extra permission: {perm_slug}")

        await db.flush()

        # ---- assign new permissions to roles ----
        roles_result = await db.execute(select(Role))
        role_map = {r.name: r for r in roles_result.scalars().all()}

        # fetch existing role_permission pairs so we don't duplicate
        existing_rp_result = await db.execute(select(role_permissions))
        existing_rp_set = {(row.role_id, row.permission_id) for row in existing_rp_result}

        new_rp_rows = []
        for role_name, perm_slugs in ROLE_PERMISSIONS_PATCH.items():
            role = role_map.get(role_name)
            if not role:
                print(f"  Role '{role_name}' not found — skipping.")
                continue
            for pslug in perm_slugs:
                perm = permission_map.get(pslug)
                if not perm:
                    print(f"    Permission '{pslug}' not in DB — skipping role link.")
                    continue
                pair = (role.id, perm.id)
                if pair not in existing_rp_set:
                    new_rp_rows.append({"role_id": role.id, "permission_id": perm.id})
                    existing_rp_set.add(pair)
                    print(f"    ✔ Linking {role_name} → {pslug}")
                else:
                    print(f"    Role-permission {role_name} → {pslug} already exists.")

        if new_rp_rows:
            await db.execute(insert(role_permissions), new_rp_rows)

        await db.commit()
        print("\n✅ Patch completed successfully.")


if __name__ == "__main__":
    asyncio.run(patch())
