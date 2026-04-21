from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.log import ActionLog
from app.schemas.log import LogFilter
from datetime import datetime, date


def _serialize_extra(extra: dict | None) -> dict | None:
    if not extra:
        return extra
    result = {}
    for k, v in extra.items():
        if isinstance(v, (datetime, date)):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def write_log(
    db: AsyncSession,
    action: str,
    user_id: int | None = None,
    site_id: int | None = None,
    detail: str | None = None,
    extra: dict | None = None,
    ip_address: str | None = None,
) -> ActionLog:
    log = ActionLog(
        user_id=user_id,
        site_id=site_id,
        action=action,
        detail=detail,
        extra=_serialize_extra(extra),
        ip_address=ip_address,
    )
    db.add(log)
    await db.flush()
    return log


async def get_logs(
    db: AsyncSession,
    filters: LogFilter,
) -> tuple[int, list[ActionLog]]:
    query = select(ActionLog).options(
        selectinload(ActionLog.user),
        selectinload(ActionLog.site),
    )
    count_query = select(func.count(ActionLog.id))

    if filters.user_id:
        query = query.where(ActionLog.user_id == filters.user_id)
        count_query = count_query.where(ActionLog.user_id == filters.user_id)
    if filters.site_id:
        query = query.where(ActionLog.site_id == filters.site_id)
        count_query = count_query.where(ActionLog.site_id == filters.site_id)
    if filters.action:
        query = query.where(ActionLog.action == filters.action)
        count_query = count_query.where(ActionLog.action == filters.action)

    total = (await db.execute(count_query)).scalar_one()
    offset = (filters.page - 1) * filters.page_size
    logs = (
        await db.execute(
            query.order_by(ActionLog.created_at.desc()).offset(offset).limit(filters.page_size)
        )
    ).scalars().all()

    return total, list(logs)
