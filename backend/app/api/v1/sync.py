from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import (
    AuthContext,
    get_client_ip,
    get_current_user,
    get_sync_auth_context,
    get_sync_columns_context,
    require_admin,
    require_manager,
)
from app.models.user import User
from app.schemas.sync import (
    SyncRequest, SyncResponse,
    HistoryResponse, HistoryEntry,
    HistoryFieldInfo,
    RollbackBatchRequest,
    RollbackEntryRequest,
    RollbackRequest,
)
from app.services.sync import process_sync
from app.services.auth import EXCEL_SYNC_TOKEN_TYPE
from app.crud.site_history import (
    capture_site_field_values,
    get_field_value_at,
    get_history_batch_entries,
    get_history_entry_by_id,
    get_history_field_meta_list,
    get_history_field_python_type,
    get_history_for_site,
    get_history_tracked_fields,
    is_history_tracked_field,
    make_history_batch_id,
    record_site_field_changes,
    serialize_history_value,
)
from app.crud.log import write_log
from app.crud.site import get_site_by_site_id, get_site_by_id
from app.core.columns import get_sync_excel_columns

router = APIRouter()


def _resolve_sync_project_id(body: SyncRequest, token_type: str | None, token_project_id: int | None) -> int | None:
    if token_type != EXCEL_SYNC_TOKEN_TYPE:
        return body.project_id

    if token_project_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if body.project_id is not None and body.project_id != token_project_id:
        raise HTTPException(status_code=403, detail="Excel sync token is scoped to another project")

    return token_project_id


async def _apply_rollback_values(
    db: AsyncSession,
    site,
    field_values: dict[str, str | None],
    user_id: int,
    batch_id: str,
    changed_at,
) -> list[str]:
    from app.crud.site import _sync_region_text
    from app.services.sync import _coerce_value

    tracked_fields = list(field_values.keys())
    if "region_id" in field_values and "region" not in tracked_fields:
        tracked_fields.append("region")

    before_values = capture_site_field_values(site, tracked_fields)

    for field, raw_value in field_values.items():
        target_type = get_history_field_python_type(field)
        if target_type is None:
            continue

        try:
            typed_value = _coerce_value(raw_value, target_type, field) if raw_value is not None else None
        except (ValueError, TypeError):
            typed_value = raw_value

        setattr(site, field, typed_value)

    if "region_id" in field_values:
        await _sync_region_text(db, site)

    changed_fields = record_site_field_changes(
        db,
        site,
        before_values,
        user_id=user_id,
        batch_id=batch_id,
        changed_at=changed_at,
    )
    if changed_fields:
        site.updated_at = changed_at

    return changed_fields


@router.post("", response_model=SyncResponse)
async def sync(
    request: Request,
    body: SyncRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_sync_auth_context),
):
    """
    Двусторонняя синхронизация Excel ↔ БД.

    - Отправить изменённые строки в rows (или пустой список для download-only)
    - Получить все строки, изменённые с last_sync_at
    """
    scoped_body = body.model_copy(
        update={
            "project_id": _resolve_sync_project_id(
                body,
                auth.token_data.token_type,
                auth.token_data.project_id,
            )
        }
    )
    result = await process_sync(db, scoped_body, auth.user.id)

    await write_log(
        db,
        user_id=auth.user.id,
        action="sync",
        detail=f"Applied: {result.applied}, conflicts: {len(result.conflicts)}, "
               f"returned: {len(result.rows)}, errors: {len(result.errors)}",
        extra={
            "applied": result.applied,
            "conflicts": len(result.conflicts),
            "returned_rows": len(result.rows),
            "client_rows": len(scoped_body.rows),
        },
        ip_address=get_client_ip(request),
    )

    await db.commit()
    return result


# Важно: статический route должен идти раньше /history/{site_id},
# иначе запрос /history-fields перехватится динамическим route и вернёт 422.
@router.get("/history-fields", response_model=list[HistoryFieldInfo])
async def history_fields(
    current_user: User = Depends(require_admin),
):
    return [HistoryFieldInfo(**item) for item in get_history_field_meta_list()]


@router.get("/history/{site_id}", response_model=HistoryResponse)
async def history(
    site_id: int,
    field_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """История изменений объекта по полям."""
    total, items = await get_history_for_site(
        db, site_id, field_name=field_name, page=page, page_size=page_size,
    )

    entries = []
    for item in items:
        entries.append(HistoryEntry(
            id=item.id,
            site_id=item.site_id,
            field_name=item.field_name,
            old_value=item.old_value,
            new_value=item.new_value,
            user_id=item.user_id,
            username=item.user.username if item.user else None,
            changed_at=item.changed_at,
            sync_batch_id=item.sync_batch_id,
        ))

    return HistoryResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=entries,
    )


@router.post("/rollback")
async def rollback(
    request: Request,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Откатить поле (или все поля) объекта к указанному моменту времени. Только admin."""
    site = await get_site_by_site_id(db, body.site_id.strip().upper())
    if not site:
        raise HTTPException(status_code=404, detail=f"Объект '{body.site_id}' не найден")

    if body.field_name and not is_history_tracked_field(body.field_name):
        raise HTTPException(status_code=400, detail=f"Поле '{body.field_name}' не поддерживает rollback")

    fields_to_rollback = [body.field_name] if body.field_name else get_history_tracked_fields()
    field_values: dict[str, str | None] = {}
    rollback_batch_id = make_history_batch_id("rollback")
    from datetime import datetime, timezone
    rollback_time = datetime.now(timezone.utc)

    for field in fields_to_rollback:
        target_type = get_history_field_python_type(field)
        if target_type is None:
            continue

        found_change, old_val = await get_field_value_at(db, site.id, field, body.to_timestamp)
        if not found_change:
            continue  # нет записей — значение не менялось после указанного момента

        current_val = getattr(site, field, None)
        if serialize_history_value(current_val) == old_val:
            continue  # уже равно

        field_values[field] = old_val

    rolled_back = await _apply_rollback_values(
        db,
        site,
        field_values,
        user_id=current_user.id,
        batch_id=rollback_batch_id,
        changed_at=rollback_time,
    )

    await write_log(
        db,
        user_id=current_user.id,
        action="rollback",
        detail=f"Rollback site {body.site_id} to {body.to_timestamp.isoformat()}",
        extra={"site_id": body.site_id, "fields": rolled_back, "history_batch_id": rollback_batch_id},
        ip_address=get_client_ip(request),
        site_id=site.id,
    )

    await db.commit()

    return {
        "success": True,
        "site_id": body.site_id,
        "rolled_back_fields": rolled_back,
        "to_timestamp": body.to_timestamp.isoformat(),
    }


@router.post("/rollback-entry")
async def rollback_entry(
    request: Request,
    body: RollbackEntryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    entry = await get_history_entry_by_id(db, body.history_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Изменение #{body.history_id} не найдено")

    site = await get_site_by_id(db, entry.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Объект для rollback не найден")

    if not is_history_tracked_field(entry.field_name):
        raise HTTPException(status_code=400, detail=f"Поле '{entry.field_name}' не поддерживает rollback")

    rollback_batch_id = make_history_batch_id("rollback")
    from datetime import datetime, timezone
    rollback_time = datetime.now(timezone.utc)
    rolled_back = await _apply_rollback_values(
        db,
        site,
        {entry.field_name: entry.old_value},
        user_id=current_user.id,
        batch_id=rollback_batch_id,
        changed_at=rollback_time,
    )

    await write_log(
        db,
        user_id=current_user.id,
        action="rollback",
        detail=f"Rollback history entry {entry.id} for site {site.site_id}",
        extra={
            "site_id": site.site_id,
            "history_id": entry.id,
            "history_batch_id": rollback_batch_id,
            "fields": rolled_back,
        },
        ip_address=get_client_ip(request),
        site_id=site.id,
    )

    await db.commit()

    return {
        "success": True,
        "site_id": site.site_id,
        "history_id": entry.id,
        "rolled_back_fields": rolled_back,
    }


@router.post("/rollback-batch")
async def rollback_batch(
    request: Request,
    body: RollbackBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    site = await get_site_by_site_id(db, body.site_id.strip().upper())
    if not site:
        raise HTTPException(status_code=404, detail=f"Объект '{body.site_id}' не найден")

    entries = await get_history_batch_entries(db, site.id, body.batch_id)
    if not entries:
        raise HTTPException(status_code=404, detail=f"Пакет изменений '{body.batch_id}' не найден")

    field_values: dict[str, str | None] = {}
    for entry in entries:
        if not is_history_tracked_field(entry.field_name):
            continue
        if entry.field_name not in field_values:
            field_values[entry.field_name] = entry.old_value

    rollback_batch_id = make_history_batch_id("rollback")
    from datetime import datetime, timezone
    rollback_time = datetime.now(timezone.utc)
    rolled_back = await _apply_rollback_values(
        db,
        site,
        field_values,
        user_id=current_user.id,
        batch_id=rollback_batch_id,
        changed_at=rollback_time,
    )

    await write_log(
        db,
        user_id=current_user.id,
        action="rollback",
        detail=f"Rollback batch {body.batch_id} for site {site.site_id}",
        extra={
            "site_id": site.site_id,
            "source_batch_id": body.batch_id,
            "history_batch_id": rollback_batch_id,
            "fields": rolled_back,
        },
        ip_address=get_client_ip(request),
        site_id=site.id,
    )

    await db.commit()

    return {
        "success": True,
        "site_id": site.site_id,
        "source_batch_id": body.batch_id,
        "rolled_back_fields": rolled_back,
    }


@router.get("/columns")
async def get_columns(
    auth: AuthContext = Depends(get_sync_columns_context),
):
    """Получить список колонок (для настройки VBA-шаблона)."""
    return [
        {
            "db_name": c.db_name,
            "excel_header": c.excel_header,
            "type": c.python_type.__name__,
            "nullable": c.nullable,
            "is_key": c.is_key,
            "group": c.group,
        }
        for c in get_sync_excel_columns()
    ]
