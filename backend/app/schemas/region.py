from pydantic import BaseModel
from datetime import datetime


class RegionCreate(BaseModel):
    name: str
    is_active: bool = True


class RegionUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class RegionOut(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
