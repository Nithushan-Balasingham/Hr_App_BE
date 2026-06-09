from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MasterModule, SubModule


async def get_navigation_tree(db: AsyncSession) -> list[MasterModule]:
    result = await db.execute(
        select(MasterModule)
        .options(
            selectinload(MasterModule.sub_modules).selectinload(SubModule.pages)
        )
        .order_by(MasterModule.sort_order)
    )
    masters = result.scalars().unique().all()

    for master in masters:
        master.sub_modules = [sm for sm in master.sub_modules if sm.is_active]
        master.sub_modules.sort(key=lambda sm: sm.sort_order)
        for sub in master.sub_modules:
            sub.pages = [p for p in sub.pages if p.is_active]
            sub.pages.sort(key=lambda p: p.sort_order)

    return [m for m in masters if any(sm.pages for sm in m.sub_modules)]
