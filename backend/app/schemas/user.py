from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from app.models.user import UserRole


def _normalize_username(v: str) -> str:
    v = v.strip()
    if len(v) < 3:
        raise ValueError("Username must be at least 3 characters")
    return v


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    return v


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None
    role: UserRole = UserRole.viewer
    contractor_id: int | None = None  # для роли contractor — привязка к компании
    project_ids: list[int] = []

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        return _normalize_username(v)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return _validate_password(v)


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None
    contractor_id: int | None = None  # для роли contractor — привязка к компании
    project_ids: list[int] | None = None

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _normalize_username(v)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_password(v)


class UserSelfUpdate(BaseModel):
    username: str | None = None
    password: str | None = None

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _normalize_username(v)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_password(v)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    contractor_id: int | None
    project_ids: list[int] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMe(UserOut):
    pass
