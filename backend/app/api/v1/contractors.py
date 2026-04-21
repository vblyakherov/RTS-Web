from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.contractor import ContractorCreate, ContractorUpdate, ContractorOut
from app.crud.contractor import (
    get_contractors, get_contractor, get_contractor_by_name,
    create_contractor, update_contractor, delete_contractor,
)
from app.crud.log import write_log
from app.api.deps import get_current_user, require_admin, require_any, get_client_ip
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=list[ContractorOut])
async def list_contractors(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    return await get_contractors(db, active_only=active_only)


@router.post("/", response_model=ContractorOut, status_code=status.HTTP_201_CREATED)
async def create_new_contractor(
    data: ContractorCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if await get_contractor_by_name(db, data.name):
        raise HTTPException(status_code=400, detail=f"Подрядчик '{data.name}' уже существует")
    contractor = await create_contractor(db, data)
    await write_log(
        db, "contractor_create", user_id=current_user.id,
        detail=f"Created contractor '{contractor.name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return contractor


@router.get("/{contractor_id}", response_model=ContractorOut)
async def get_contractor_detail(
    contractor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    contractor = await get_contractor(db, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Подрядчик не найден")
    return contractor


@router.patch("/{contractor_id}", response_model=ContractorOut)
async def update_existing_contractor(
    contractor_id: int,
    data: ContractorUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    contractor = await get_contractor(db, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Подрядчик не найден")
    if data.name and data.name != contractor.name:
        existing = await get_contractor_by_name(db, data.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Подрядчик '{data.name}' уже существует")
    updated = await update_contractor(db, contractor, data)
    await write_log(
        db, "contractor_update", user_id=current_user.id,
        detail=f"Updated contractor '{updated.name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return updated


@router.delete("/{contractor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_contractor(
    contractor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    contractor = await get_contractor(db, contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Подрядчик не найден")
    name = contractor.name
    await delete_contractor(db, contractor)
    await write_log(
        db, "contractor_delete", user_id=current_user.id,
        detail=f"Deleted contractor '{name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
