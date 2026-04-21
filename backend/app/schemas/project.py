from datetime import datetime

from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    module_key: str = "placeholder"
    template_key: str | None = None
    is_active: bool = True
    sort_order: int = 100

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-").replace("_", "-")
        if not normalized:
            raise ValueError("Project code is required")
        return normalized


class ProjectUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    module_key: str | None = None
    template_key: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "-").replace("_", "-")
        if not normalized:
            raise ValueError("Project code is required")
        return normalized


class ProjectOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    module_key: str
    template_key: str | None
    is_active: bool
    is_configured: bool
    sort_order: int
    site_count: int = 0
    assigned_user_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectShort(BaseModel):
    id: int
    name: str
    code: str
    module_key: str
    is_configured: bool

    model_config = {"from_attributes": True}
