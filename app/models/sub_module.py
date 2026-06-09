from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubModule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sub_modules"

    master_module_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("master_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    master_module: Mapped["MasterModule"] = relationship("MasterModule", back_populates="sub_modules")
    pages: Mapped[list["SubModulePage"]] = relationship(
        "SubModulePage",
        back_populates="sub_module",
        cascade="all, delete-orphan",
        order_by="SubModulePage.sort_order",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        back_populates="sub_module",
        cascade="all, delete-orphan",
    )
