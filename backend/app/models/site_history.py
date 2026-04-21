from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database import Base


class SiteHistory(Base):
    __tablename__ = "site_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sync_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    site = relationship("Site", backref="history_entries")
    user = relationship("User")

    __table_args__ = (
        Index("ix_site_history_site_changed", "site_id", "changed_at"),
        Index("ix_site_history_batch", "sync_batch_id"),
        Index("ix_site_history_field", "site_id", "field_name"),
    )
