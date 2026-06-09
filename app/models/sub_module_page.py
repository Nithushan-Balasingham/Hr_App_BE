from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubModulePage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sub_module_pages"

    sub_module_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sub_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    route_path: Mapped[str] = mapped_column(String(255), nullable=False)
    permission_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sub_module: Mapped["SubModule"] = relationship("SubModule", back_populates="pages")
