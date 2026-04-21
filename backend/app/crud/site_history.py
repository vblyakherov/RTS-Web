from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy import DateTime as SADateTime, Enum as SAEnum, Float as SAFloat, Integer as SAInteger, Numeric as SANumeric
from app.core.columns import get_column_by_db_name, get_sync_excel_columns
from app.models.site import Site, SiteStatus
from app.models.site_history import SiteHistory
from app.models.user import User

_HISTORY_EXCLUDED_FIELDS = {"id", "site_id", "created_at", "updated_at"}
_EXTRA_HISTORY_FIELD_META: dict[str, tuple[str, str, str]] = {
    "region_id": ("Регион", "int", "Основная информация"),
    "address": ("Адрес", "str", "Основная информация"),
    "status": ("Статус", "enum", "Статус и назначение"),
    "contractor_id": ("Подрядчик", "int", "Статус и назначение"),
    "notes": ("Заметки", "str", "Заметки"),
}


def make_history_batch_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def get_history_tracked_fields() -> list[str]:
    tracked_fields = [
        column.db_name
        for column in get_sync_excel_columns()
        if not column.is_key and column.db_name not in _HISTORY_EXCLUDED_FIELDS
    ]
    tracked_fields.extend(
        field_name
        for field_name in _EXTRA_HISTORY_FIELD_META
        if field_name not in tracked_fields and field_name in Site.__table__.columns
    )
    return tracked_fields


def is_history_tracked_field(field_name: str) -> bool:
    return field_name in set(get_history_tracked_fields())


def get_history_field_meta(field_name: str) -> dict[str, str]:
    if field_name in _EXTRA_HISTORY_FIELD_META:
        label, value_type, group = _EXTRA_HISTORY_FIELD_META[field_name]
        return {
            "field_name": field_name,
            "label": label,
            "type": value_type,
            "group": group,
        }

    col_def = get_column_by_db_name(field_name)
    if col_def is not None:
        value_type = "enum" if field_name == "status" else col_def.python_type.__name__
        return {
            "field_name": field_name,
            "label": col_def.excel_header,
            "type": value_type,
            "group": col_def.group or "Прочее",
        }

    py_type = get_history_field_python_type(field_name)
    value_type = py_type.__name__ if py_type is not None and hasattr(py_type, "__name__") else "str"
    return {
        "field_name": field_name,
        "label": field_name,
        "type": value_type,
        "group": "Прочее",
    }


def get_history_field_meta_list() -> list[dict[str, str]]:
    return [get_history_field_meta(field_name) for field_name in get_history_tracked_fields()]


def get_history_field_python_type(field_name: str) -> type | None:
    if not is_history_tracked_field(field_name):
        return None

    column = Site.__table__.columns[field_name]
    if field_name == "status":
        return SiteStatus
    if isinstance(column.type, SAEnum) and column.type.enum_class:
        return column.type.enum_class
    if isinstance(column.type, SADateTime):
        return datetime
    if isinstance(column.type, SAInteger):
        return int
    if isinstance(column.type, SAFloat):
        return float
    if isinstance(column.type, SANumeric):
        return Decimal

    try:
        return column.type.python_type
    except (AttributeError, NotImplementedError):
        return str


def capture_site_field_values(
    site: Site,
    field_names: Iterable[str],
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    seen: set[str] = set()
    for field_name in field_names:
        if field_name in seen or not hasattr(site, field_name):
            continue
        snapshot[field_name] = getattr(site, field_name)
        seen.add(field_name)
    return snapshot


def serialize_history_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, SiteStatus):
        return value.value
    return str(value)


def record_site_field_changes(
    db: AsyncSession,
    site: Site,
    before_values: dict[str, Any],
    user_id: int | None = None,
    batch_id: str | None = None,
    changed_at: datetime | None = None,
) -> list[str]:
    timestamp = changed_at or datetime.now(timezone.utc)
    changed_fields: list[str] = []

    for field_name, old_value in before_values.items():
        new_value = getattr(site, field_name, None)
        if serialize_history_value(old_value) == serialize_history_value(new_value):
            continue

        db.add(SiteHistory(
            site=site,
            field_name=field_name,
            old_value=serialize_history_value(old_value),
            new_value=serialize_history_value(new_value),
            user_id=user_id,
            sync_batch_id=batch_id,
            changed_at=timestamp,
        ))
        changed_fields.append(field_name)

    return changed_fields


def record_site_creation(
    db: AsyncSession,
    site: Site,
    field_names: Iterable[str] | None = None,
    user_id: int | None = None,
    batch_id: str | None = None,
    changed_at: datetime | None = None,
) -> list[str]:
    tracked_fields = list(field_names) if field_names is not None else get_history_tracked_fields()
    initial_values = {
        field_name: None
        for field_name in tracked_fields
        if hasattr(site, field_name)
        and serialize_history_value(getattr(site, field_name)) is not None
    }
    return record_site_field_changes(
        db,
        site,
        initial_values,
        user_id=user_id,
        batch_id=batch_id,
        changed_at=changed_at,
    )


async def get_history_for_site(
    db: AsyncSession,
    site_id: int,
    field_name: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[SiteHistory]]:
    base = select(SiteHistory).where(SiteHistory.site_id == site_id)
    count_q = select(func.count(SiteHistory.id)).where(SiteHistory.site_id == site_id)

    if field_name:
        base = base.where(SiteHistory.field_name == field_name)
        count_q = count_q.where(SiteHistory.field_name == field_name)

    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base.options(selectinload(SiteHistory.user))
        .order_by(SiteHistory.changed_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    return total, items


async def get_history_entry_by_id(
    db: AsyncSession,
    entry_id: int,
) -> SiteHistory | None:
    result = await db.execute(
        select(SiteHistory)
        .options(selectinload(SiteHistory.user))
        .where(SiteHistory.id == entry_id)
    )
    return result.scalar_one_or_none()


async def get_history_batch_entries(
    db: AsyncSession,
    site_id: int,
    batch_id: str,
) -> list[SiteHistory]:
    result = await db.execute(
        select(SiteHistory)
        .where(
            SiteHistory.site_id == site_id,
            SiteHistory.sync_batch_id == batch_id,
        )
        .order_by(SiteHistory.changed_at.asc(), SiteHistory.id.asc())
    )
    return list(result.scalars().all())


async def get_field_value_at(
    db: AsyncSession,
    site_id: int,
    field_name: str,
    at_timestamp,
) -> tuple[bool, str | None]:
    """Получить значение поля на указанный момент времени.

    Возвращает `(found_change_after_timestamp, value_at_timestamp)`.
    Это позволяет отличить "после даты не было изменений" от
    "значение на дату было NULL".
    """
    result = await db.execute(
        select(SiteHistory)
        .where(
            SiteHistory.site_id == site_id,
            SiteHistory.field_name == field_name,
            SiteHistory.changed_at >= at_timestamp,
        )
        .order_by(SiteHistory.changed_at.asc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    if entry:
        return True, entry.old_value
    # Нет записей после at_timestamp — текущее значение и есть нужное
    return False, None
