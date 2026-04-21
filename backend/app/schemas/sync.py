from pydantic import BaseModel
from datetime import datetime
from typing import Any


class SyncRequest(BaseModel):
    last_sync_at: datetime | None = None
    project_id: int | None = None
    rows: list[dict[str, Any]] = []
    client_version: int = 1


class ConflictInfo(BaseModel):
    site_id: str
    fields: list[str]
    server_updated_at: datetime


class SyncResponse(BaseModel):
    server_time: datetime
    applied: int
    conflicts: list[ConflictInfo] = []
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    deleted_site_ids: list[str] = []


class HistoryEntry(BaseModel):
    id: int
    site_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    user_id: int | None
    username: str | None = None
    changed_at: datetime
    sync_batch_id: str | None

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[HistoryEntry]


class HistoryFieldInfo(BaseModel):
    field_name: str
    label: str
    type: str
    group: str


class RollbackRequest(BaseModel):
    site_id: str
    field_name: str | None = None
    to_timestamp: datetime


class RollbackBatchRequest(BaseModel):
    site_id: str
    batch_id: str


class RollbackEntryRequest(BaseModel):
    history_id: int
