import contextvars
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.db.session import get_db
from app.models import Role, User

request_ip_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_ip", default=None)
request_user_agent_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_user_agent", default=None)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials, TOKEN_TYPE_ACCESS)
        user_id = payload.get("sub")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def user_permission_slugs(user: User) -> set[str]:
    if user.role.is_super_admin:
        return set()
    return {perm.slug for perm in user.role.permissions}


def user_has_permission(user: User, *slugs: str) -> bool:
    if user.role.is_super_admin:
        return True
    if not slugs:
        return True
    user_slugs = user_permission_slugs(user)
    return any(slug in user_slugs for slug in slugs)


def require_permissions(*slugs: str):
    async def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if not user_has_permission(current_user, *slugs):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def get_request_ip() -> str | None:
    return request_ip_ctx.get()


def get_request_user_agent() -> str | None:
    return request_user_agent_ctx.get()
