"""
Сервис двусторонней синхронизации Excel ↔ БД.

Протокол:
1. Клиент отправляет changed rows + last_sync_at
2. Сервер применяет изменения (last-write-wins), записывает историю
3. Сервер возвращает все строки, изменённые с last_sync_at
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.site import Site, SiteStatus
from app.models.project import Project
from app.models.site_history import SiteHistory
from app.models.region import Region
from app.core.columns import SITE_COLUMNS, get_syncable_db_names, get_column_by_db_name
from app.schemas.sync import SyncRequest, SyncResponse, ConflictInfo
from app.services.ucn_template import apply_template_derivations
from app.services.reference_sync import sync_regions_from_sites


# Множество допустимых db_name для валидации входящих данных
_VALID_DB_NAMES = {c.db_name for c in SITE_COLUMNS}

# Множество полей, которые можно обновлять (всё кроме ключа site_id)
_UPDATABLE_FIELDS = {c.db_name for c in SITE_COLUMNS if not c.is_key}

STATUS_LABELS = {
    SiteStatus.planned: "Запланирован",
    SiteStatus.survey: "Обследование",
    SiteStatus.design: "Проектирование",
    SiteStatus.permitting: "Разрешения",
    SiteStatus.construction: "Строительство",
    SiteStatus.testing: "Тестирование",
    SiteStatus.accepted: "Принят",
    SiteStatus.cancelled: "Отменён",
}
STATUS_REVERSE = {value: key for key, value in STATUS_LABELS.items()}


async def process_sync(
    db: AsyncSession,
    request: SyncRequest,
    user_id: int,
) -> SyncResponse:
    server_time = datetime.now(timezone.utc)
    batch_id = uuid.uuid4().hex[:16]
    sync_project_id = request.project_id or await _get_default_sync_project_id(db)

    applied = 0
    conflicts: list[ConflictInfo] = []
    errors: list[str] = []

    if request.rows:
        applied, conflicts, errors = await _apply_client_rows(
            db,
            request.rows,
            request.last_sync_at,
            user_id,
            batch_id,
            server_time,
            project_id=sync_project_id,
        )
        await db.flush()
        await sync_regions_from_sites(db)
        await db.flush()

    # Получить все строки, изменённые с last_sync_at (или все, если первая синхронизация)
    rows = await _get_updated_rows(db, request.last_sync_at, project_id=sync_project_id)

    return SyncResponse(
        server_time=server_time,
        applied=applied,
        conflicts=conflicts,
        rows=rows,
        errors=errors,
    )


async def _apply_client_rows(
    db: AsyncSession,
    rows: list[dict[str, Any]],
    last_sync_at: datetime | None,
    user_id: int,
    batch_id: str,
    server_time: datetime,
    project_id: int | None = None,
) -> tuple[int, list[ConflictInfo], list[str]]:
    applied = 0
    conflicts: list[ConflictInfo] = []
    errors: list[str] = []

    # Собрать все site_id из входящих строк
    incoming_site_ids = []
    for row in rows:
        sid = str(row.get("site_id", "")).strip().upper()
        if sid:
            incoming_site_ids.append(sid)

    # Загрузить существующие записи одним запросом
    existing_map: dict[str, Site] = {}
    if incoming_site_ids:
        result = await db.execute(
            select(Site).where(Site.site_id.in_(incoming_site_ids))
        )
        for s in result.scalars().all():
            existing_map[s.site_id] = s

    # Кэш регионов
    region_cache: dict[str, int] = {}

    for i, row in enumerate(rows):
        site_id = str(row.get("site_id", "")).strip().upper()
        if not site_id:
            errors.append(f"Строка {i + 1}: отсутствует site_id — пропущена")
            continue

        site = existing_map.get(site_id)
        if site is None:
            errors.append(
                f"Строка {i + 1} ({site_id}): объект не найден; создание новых объектов через Excel запрещено"
            )
            continue

        if project_id is not None:
            if site.project_id is None:
                site.project_id = project_id
            elif site.project_id != project_id:
                errors.append(
                    f"Строка {i + 1} ({site_id}): объект относится к другому проекту"
                )
                continue

        # Отфильтровать только допустимые поля
        clean_data = _clean_row(row, errors, i)
        if clean_data is None:
            continue

        clean_data["site_id"] = site_id
        clean_data = apply_template_derivations(clean_data, site=existing_map.get(site_id))
        clean_data.pop("site_id", None)

        # Резолвить region → region_id
        region_name = clean_data.get("region")
        if region_name:
            region_id = await _resolve_region(db, region_name, region_cache)
            if region_id:
                clean_data["region_id"] = region_id

        # UPDATE
        # Проверка конфликта (информационно)
        if last_sync_at and site.updated_at and site.updated_at > last_sync_at:
            conflict_fields = _detect_conflict_fields(site, clean_data)
            if conflict_fields:
                conflicts.append(ConflictInfo(
                    site_id=site_id,
                    fields=conflict_fields,
                    server_updated_at=site.updated_at,
                ))

        # Записать историю и применить изменения
        await _apply_and_record(db, site, clean_data, user_id, batch_id, server_time)
        applied += 1

    return applied, conflicts, errors


def _clean_row(
    row: dict[str, Any],
    errors: list[str],
    index: int,
) -> dict[str, Any] | None:
    """Отфильтровать и привести типы полей входящей строки."""
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if key == "site_id":
            continue
        if key not in _UPDATABLE_FIELDS:
            continue

        col_def = get_column_by_db_name(key)
        if col_def is None:
            continue

        if value is None or (isinstance(value, str) and value.strip() == ""):
            clean[key] = None
            continue

        try:
            clean[key] = _coerce_value(value, col_def.python_type, key)
        except (ValueError, TypeError) as e:
            errors.append(f"Строка {index + 1}, поле '{key}': {e}")

    return clean if clean else None


def _coerce_value(value: Any, target_type: type, field_name: str) -> Any:
    """Привести значение к нужному типу."""
    if target_type == datetime:
        if isinstance(value, datetime):
            return value
        s = str(value).strip()
        iso_candidate = s[:-1] + "+00:00" if s.endswith("Z") else s
        try:
            return datetime.fromisoformat(iso_candidate)
        except ValueError:
            pass
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"не удалось распознать дату '{value}'")

    if target_type == float:
        return float(value)

    if target_type == int:
        return int(value)

    if target_type == Decimal:
        return Decimal(str(value).strip())

    if field_name == "status":
        # Принимаем как enum-значение, так и русские названия
        if isinstance(value, SiteStatus):
            return value
        s = str(value).strip().lower()
        try:
            return SiteStatus(s)
        except ValueError:
            status = STATUS_REVERSE.get(str(value).strip())
            if status:
                return status
            raise ValueError(f"неизвестный статус '{value}'")

    # str
    return str(value).strip()


def _detect_conflict_fields(site: Site, changes: dict[str, Any]) -> list[str]:
    """Найти поля, которые изменились и на сервере, и у клиента."""
    conflict_fields = []
    for field, new_value in changes.items():
        current = getattr(site, field, None)
        if _to_str(current) != _to_str(new_value):
            conflict_fields.append(field)
    return conflict_fields


async def _apply_and_record(
    db: AsyncSession,
    site: Site,
    changes: dict[str, Any],
    user_id: int,
    batch_id: str,
    server_time: datetime,
) -> None:
    """Применить изменения к объекту и записать историю."""
    for field, new_value in changes.items():
        if not hasattr(site, field):
            continue
        old_value = getattr(site, field)
        if _to_str(old_value) == _to_str(new_value):
            continue  # значение не изменилось

        # Записать историю
        db.add(SiteHistory(
            site_id=site.id,
            field_name=field,
            old_value=_to_str(old_value),
            new_value=_to_str(new_value),
            user_id=user_id,
            sync_batch_id=batch_id,
            changed_at=server_time,
        ))

        setattr(site, field, new_value)

    site.updated_at = server_time


async def _get_updated_rows(
    db: AsyncSession,
    since: datetime | None,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """Получить все строки, обновлённые с указанного момента."""
    query = select(Site).options(
        selectinload(Site.contractor),
        selectinload(Site.region_rel),
    )
    if project_id is not None:
        query = query.where(Site.project_id == project_id)
    if since:
        query = query.where(Site.updated_at > since)

    query = query.order_by(Site.site_id)
    result = await db.execute(query)
    sites = result.scalars().all()

    rows = []
    for site in sites:
        row = _site_to_dict(site)
        rows.append(row)

    return rows


async def _get_default_sync_project_id(db: AsyncSession) -> int | None:
    result = await db.execute(
        select(Project.id)
        .where(Project.module_key == "ucn_sites_v1")
        .order_by(Project.sort_order.asc(), Project.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _site_to_dict(site: Site) -> dict[str, Any]:
    """Сериализовать Site в словарь для ответа клиенту."""
    row: dict[str, Any] = {"site_id": site.site_id}

    for col in SITE_COLUMNS:
        value = getattr(site, col.db_name, None)
        if isinstance(value, datetime):
            row[col.db_name] = value.isoformat()
        elif isinstance(value, SiteStatus):
            row[col.db_name] = value.value
        else:
            row[col.db_name] = value

    # Добавить вспомогательные поля
    row["_id"] = site.id
    row["_updated_at"] = site.updated_at.isoformat() if site.updated_at else None
    row["_contractor_name"] = site.contractor.name if site.contractor else None
    row["_region_name"] = site.region_rel.name if site.region_rel else site.region
    row["_status_label"] = STATUS_LABELS.get(site.status, site.status.value if site.status else "")

    return row


async def _resolve_region(
    db: AsyncSession,
    region_name: str,
    cache: dict[str, int],
) -> int | None:
    if region_name in cache:
        return cache[region_name]

    result = await db.execute(
        select(Region).where(Region.name == region_name)
    )
    region = result.scalar_one_or_none()
    if region:
        cache[region_name] = region.id
        return region.id
    return None


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, SiteStatus):
        return value.value
    return str(value)
