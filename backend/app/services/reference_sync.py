from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.region import Region
from app.models.site import Site


def _normalize_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def sync_reference_directories(db: AsyncSession) -> None:
    await sync_regions_from_sites(db)


async def sync_regions_from_sites(db: AsyncSession) -> None:
    region_names_result = await db.execute(
        select(Site.region).where(func.length(func.trim(func.coalesce(Site.region, ""))) > 0).distinct()
    )
    used_names = sorted(
        {
            normalized
            for (name,) in region_names_result
            if (normalized := _normalize_name(name)) is not None
        }
    )

    existing_regions = list((await db.execute(select(Region))).scalars().all())
    regions_by_name = {_normalize_name(region.name): region for region in existing_regions}

    for name in used_names:
        region = regions_by_name.get(name)
        if region is None:
            region = Region(name=name, is_active=True)
            db.add(region)
            await db.flush()
            regions_by_name[name] = region

        await db.execute(
            update(Site)
            .where(func.trim(func.coalesce(Site.region, "")) == name)
            .where((Site.region_id.is_(None)) | (Site.region_id != region.id))
            .values(region_id=region.id)
        )

    for region in existing_regions:
        normalized_name = _normalize_name(region.name)
        if normalized_name and region.name != normalized_name:
            region.name = normalized_name

    await db.flush()


async def sync_contractors_from_sites(db: AsyncSession) -> None:
    """
    Contractor activity is managed manually through the directory UI.

    We intentionally do not recalculate is_active from Site usage, because that
    would overwrite explicit admin changes.
    """
    return None
