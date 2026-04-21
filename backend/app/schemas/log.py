from pydantic import BaseModel
from datetime import datetime


class LogOut(BaseModel):
    id: int
    user_id: int | None
    site_id: int | None
    action: str
    detail: str | None
    extra: dict | None
    ip_address: str | None
    created_at: datetime

    # Вложенные данные для удобства
    username: str | None = None
    site_id_str: str | None = None  # human-readable site_id

    model_config = {"from_attributes": True}


class LogFilter(BaseModel):
    user_id: int | None = None
    site_id: int | None = None
    action: str | None = None
    page: int = 1
    page_size: int = 50
