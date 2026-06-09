from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import Role, User
from app.schemas.common import AuthMeResponse, LoginRequest, MessageResponse, PermissionOut, RoleOut, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role=RoleOut(
            id=user.role.id,
            name=user.role.name,
            description=user.role.description,
            is_super_admin=user.role.is_super_admin,
            permissions=[
                PermissionOut(id=p.id, name=p.name, slug=p.slug, description=p.description)
                for p in user.role.permissions
            ],
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.email == payload.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    settings = get_settings()
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    settings = get_settings()
    cookie_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
    try:
        payload = decode_token(cookie_token, TOKEN_TYPE_REFRESH)
        user_id = payload.get("sub")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    settings = get_settings()
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/auth")
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=AuthMeResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    permissions = [] if current_user.role.is_super_admin else [p.slug for p in current_user.role.permissions]
    return AuthMeResponse(
        user=_serialize_user(current_user),
        permissions=permissions,
        is_super_admin=current_user.role.is_super_admin,
    )
