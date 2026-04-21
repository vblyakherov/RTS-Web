from sqlalchemy import String, Enum, Boolean, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    contractor = "contractor"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(256), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.viewer, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Для пользователей с ролью contractor — ссылка на компанию-подрядчика
    contractor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contractor_company = relationship("Contractor", back_populates="users", foreign_keys=[contractor_id])
    projects = relationship("Project", secondary="user_projects", back_populates="users")
    logs = relationship("ActionLog", back_populates="user")

    @property
    def project_ids(self) -> list[int]:
        return [project.id for project in self.projects]
