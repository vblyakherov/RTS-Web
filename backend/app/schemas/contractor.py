from pydantic import BaseModel
from datetime import datetime


class ContractorCreate(BaseModel):
    name: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_active: bool = True


class ContractorUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ContractorOut(BaseModel):
    id: int
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
