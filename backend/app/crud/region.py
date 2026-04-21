from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.region import Region
from app.schemas.region import RegionCreate, RegionUpdate


async def get_regions(
    db: AsyncSession,
    active_only: bool = False,
) -> list[Region]:
    q = select(Region)
    if active_only:
        q = q.where(Region.is_active == True)  # noqa: E712
    q = q.order_by(Region.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_region(db: AsyncSession, region_id: int) -> Region | None:
    return await db.get(Region, region_id)


async def get_region_by_name(db: AsyncSession, name: str) -> Region | None:
    result = await db.execute(select(Region).where(Region.name == name))
    return result.scalar_one_or_none()


async def create_region(db: AsyncSession, data: RegionCreate) -> Region:
    region = Region(**data.model_dump())
    db.add(region)
    await db.flush()
    await db.refresh(region)
    return region


async def update_region(
    db: AsyncSession, region: Region, data: RegionUpdate
) -> Region:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(region, field, value)
    await db.flush()
    await db.refresh(region)
    return region


async def delete_region(db: AsyncSession, region: Region) -> None:
    await db.delete(region)
    await db.flush()
