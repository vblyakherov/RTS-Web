from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.log import LogFilter, LogOut
from app.crud.log import get_logs
from app.api.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=list[LogOut])
async def list_logs(
    user_id: int | None = None,
    site_id: int | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    filters = LogFilter(
        user_id=user_id,
        site_id=site_id,
        action=action,
        page=page,
        page_size=page_size,
    )
    _, logs = await get_logs(db, filters)

    result = []
    for log in logs:
        item = LogOut(
            id=log.id,
            user_id=log.user_id,
            site_id=log.site_id,
            action=log.action,
            detail=log.detail,
            extra=log.extra,
            ip_address=log.ip_address,
            created_at=log.created_at,
            username=log.user.username if log.user else None,
            site_id_str=log.site.site_id if log.site else None,
        )
        result.append(item)
    return result
