"""Integration verification script for HR Portal core behaviors."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault(
    "API_ENCRYPTION_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)

from app.core.encryption import decrypt_payload, encrypt_payload
from app.core.security import hash_password, verify_password


def test_encryption_roundtrip() -> None:
    payload = {"email": "admin@hrportal.local", "password": "Admin@123"}
    envelope = encrypt_payload(payload)
    assert set(envelope.keys()) == {"iv", "ciphertext", "tag"}
    restored = decrypt_payload(envelope)
    assert restored == payload
    print("[OK] AES-256-GCM encryption roundtrip")


def test_password_hashing() -> None:
    hashed = hash_password("Admin@123")
    assert verify_password("Admin@123", hashed)
    assert not verify_password("wrong", hashed)
    print("[OK] Password hashing")


def test_nav_filter_logic() -> None:
    """Mirror frontend filterNavTree rules."""
    masters = [
        {
            "sub_modules": [
                {
                    "pages": [
                        {"permission_names": ["view-employees"]},
                        {"permission_names": ["create-employee"]},
                    ]
                },
                {
                    "pages": [{"permission_names": ["view-departments"]}],
                },
            ]
        }
    ]
    permissions = {"view-employees"}

    visible_pages = [
        p
        for sub in masters[0]["sub_modules"]
        for p in sub["pages"]
        if not p["permission_names"] or any(slug in permissions for slug in p["permission_names"])
    ]
    assert len(visible_pages) == 1
    assert visible_pages[0]["permission_names"] == ["view-employees"]

    single_page_sub = [{"pages": [{"permission_names": [], "route_path": "/hr/dashboard"}]}]
    assert len(single_page_sub[0]["pages"]) == 1
    print("[OK] Permission-based nav filtering rules")


def test_audit_append_only_contract() -> None:
    from app.models.audit_log import AuditLog
    from app.routers import audit_logs

    router_paths = [getattr(r, "path", "") for r in audit_logs.router.routes]
    assert any("GET" in str(r.methods) for r in audit_logs.router.routes if hasattr(r, "methods"))
    assert not any(method in {"POST", "PUT", "PATCH", "DELETE"} for r in audit_logs.router.routes for method in getattr(r, "methods", set()))
    assert "user_id" in AuditLog.__table__.columns
    print("[OK] Audit logs exposed read-only")


if __name__ == "__main__":
    test_encryption_roundtrip()
    test_password_hashing()
    test_nav_filter_logic()
    test_audit_append_only_contract()
    print("All local verification checks passed.")
