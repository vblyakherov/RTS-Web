from pydantic import BaseModel, field_validator
from datetime import datetime
from app.models.site import SiteStatus


class ProjectShort(BaseModel):
    id: int
    name: str
    code: str
    module_key: str
    is_configured: bool

    model_config = {"from_attributes": True}


class ContractorShort(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class RegionShort(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class SiteCreate(BaseModel):
    site_id: str
    name: str
    project_id: int
    region: str | None = None      # текст (для Excel / ручного ввода)
    region_id: int | None = None   # FK на справочник (предпочтительно)
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: SiteStatus = SiteStatus.planned
    contractor_id: int | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    notes: str | None = None

    @field_validator("site_id")
    @classmethod
    def site_id_strip(cls, v: str) -> str:
        return v.strip().upper()


class SiteUpdate(BaseModel):
    name: str | None = None
    project_id: int | None = None
    region: str | None = None
    region_id: int | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: SiteStatus | None = None
    contractor_id: int | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    notes: str | None = None


class SiteOut(BaseModel):
    id: int
    site_id: str
    name: str
    project_id: int | None
    project: ProjectShort | None
    region: str | None
    region_id: int | None
    region_rel: RegionShort | None
    address: str | None
    latitude: float | None
    longitude: float | None
    status: SiteStatus
    contractor_id: int | None
    contractor: ContractorShort | None
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SiteListItem(BaseModel):
    """Лёгкая версия для списка (без тяжёлых полей)"""
    id: int
    site_id: str
    name: str
    project_id: int | None
    project: ProjectShort | None
    region: str | None
    region_id: int | None
    region_rel: RegionShort | None
    status: SiteStatus
    contractor: ContractorShort | None
    planned_end: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SiteFilter(BaseModel):
    project_id: int | None = None
    region: str | None = None
    region_id: int | None = None
    status: SiteStatus | None = None
    contractor_id: int | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 50

    @field_validator("page_size")
    @classmethod
    def limit_page_size(cls, v: int) -> int:
        return min(v, 200)


class SiteListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SiteListItem]
