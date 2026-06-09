from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import MasterModuleOut
from app.services.nav_service import get_navigation_tree

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("/nav", response_model=list[MasterModuleOut])
async def get_nav(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    masters = await get_navigation_tree(db)
    return masters
