from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.region import RegionCreate, RegionUpdate, RegionOut
from app.crud.region import (
    get_regions, get_region, get_region_by_name,
    create_region, update_region, delete_region,
)
from app.crud.log import write_log
from app.api.deps import get_current_user, require_admin, require_any, get_client_ip
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=list[RegionOut])
async def list_regions(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    return await get_regions(db, active_only=active_only)


@router.post("/", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
async def create_new_region(
    data: RegionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if await get_region_by_name(db, data.name):
        raise HTTPException(status_code=400, detail=f"Регион '{data.name}' уже существует")
    region = await create_region(db, data)
    await write_log(
        db, "region_create", user_id=current_user.id,
        detail=f"Created region '{region.name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return region


@router.get("/{region_id}", response_model=RegionOut)
async def get_region_detail(
    region_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    region = await get_region(db, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Регион не найден")
    return region


@router.patch("/{region_id}", response_model=RegionOut)
async def update_existing_region(
    region_id: int,
    data: RegionUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    region = await get_region(db, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Регион не найден")
    if data.name and data.name != region.name:
        existing = await get_region_by_name(db, data.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Регион '{data.name}' уже существует")
    updated = await update_region(db, region, data)
    await write_log(
        db, "region_update", user_id=current_user.id,
        detail=f"Updated region '{updated.name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return updated


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_region(
    region_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    region = await get_region(db, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Регион не найден")
    name = region.name
    await delete_region(db, region)
    await write_log(
        db, "region_delete", user_id=current_user.id,
        detail=f"Deleted region '{name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
