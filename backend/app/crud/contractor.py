from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.contractor import Contractor
from app.schemas.contractor import ContractorCreate, ContractorUpdate


async def get_contractors(
    db: AsyncSession,
    active_only: bool = False,
) -> list[Contractor]:
    q = select(Contractor)
    if active_only:
        q = q.where(Contractor.is_active == True)  # noqa: E712
    q = q.order_by(Contractor.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_contractor(db: AsyncSession, contractor_id: int) -> Contractor | None:
    return await db.get(Contractor, contractor_id)


async def get_contractor_by_name(db: AsyncSession, name: str) -> Contractor | None:
    result = await db.execute(select(Contractor).where(Contractor.name == name))
    return result.scalar_one_or_none()


async def create_contractor(db: AsyncSession, data: ContractorCreate) -> Contractor:
    contractor = Contractor(**data.model_dump())
    db.add(contractor)
    await db.flush()
    await db.refresh(contractor)
    return contractor


async def update_contractor(
    db: AsyncSession, contractor: Contractor, data: ContractorUpdate
) -> Contractor:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(contractor, field, value)
    await db.flush()
    await db.refresh(contractor)
    return contractor


async def delete_contractor(db: AsyncSession, contractor: Contractor) -> None:
    await db.delete(contractor)
    await db.flush()
