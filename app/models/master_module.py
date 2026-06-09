from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MasterModule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "master_modules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sub_modules: Mapped[list["SubModule"]] = relationship(
        "SubModule",
        back_populates="master_module",
        cascade="all, delete-orphan",
        order_by="SubModule.sort_order",
    )
