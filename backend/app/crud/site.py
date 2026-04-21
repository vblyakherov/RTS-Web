from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.models.site import Site, SiteStatus
from app.models.region import Region
from app.schemas.site import SiteCreate, SiteUpdate, SiteFilter
from app.crud.site_history import (
    capture_site_field_values,
    make_history_batch_id,
    record_site_creation,
    record_site_field_changes,
)
from app.services.ucn_template import apply_template_derivations


def _base_query():
    return select(Site).options(
        selectinload(Site.project),
        selectinload(Site.contractor),
        selectinload(Site.region_rel),
    )


async def get_site_by_id(db: AsyncSession, site_id: int) -> Site | None:
    result = await db.execute(_base_query().where(Site.id == site_id))
    return result.scalar_one_or_none()


async def get_site_by_site_id(db: AsyncSession, site_id: str) -> Site | None:
    result = await db.execute(_base_query().where(Site.site_id == site_id))
    return result.scalar_one_or_none()


async def get_sites(
    db: AsyncSession,
    filters: SiteFilter,
    contractor_id_filter: int | None = None,  # для роли contractor (contractor_id компании)
) -> tuple[int, list[Site]]:
    query = _base_query()
    count_query = select(func.count(Site.id))

    conditions = []
    if filters.project_id:
        conditions.append(Site.project_id == filters.project_id)
    if filters.region_id:
        conditions.append(Site.region_id == filters.region_id)
    elif filters.region:
        conditions.append(Site.region.ilike(f"%{filters.region}%"))
    if filters.status:
        conditions.append(Site.status == filters.status)
    if filters.contractor_id:
        conditions.append(Site.contractor_id == filters.contractor_id)
    if contractor_id_filter:
        conditions.append(Site.contractor_id == contractor_id_filter)
    if filters.search:
        like = f"%{filters.search}%"
        conditions.append(
            or_(
                Site.site_id.ilike(like),
                Site.name.ilike(like),
                Site.address.ilike(like),
            )
        )

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar_one()
    offset = (filters.page - 1) * filters.page_size
    sites = (
        await db.execute(query.order_by(Site.updated_at.desc()).offset(offset).limit(filters.page_size))
    ).scalars().all()

    return total, list(sites)


async def get_all_sites_for_export(
    db: AsyncSession,
    project_id: int,
    contractor_id_filter: int | None = None,
) -> list[Site]:
    """Без пагинации — для экспорта в Excel"""
    query = _base_query().where(Site.project_id == project_id)
    if contractor_id_filter:
        query = query.where(Site.contractor_id == contractor_id_filter)
    result = await db.execute(query.order_by(Site.site_id))
    return list(result.scalars().all())


async def _sync_region_text(db: AsyncSession, site: Site) -> None:
    """Если задан region_id — синхронизируем текстовое поле region из Region.name"""
    if site.region_id:
        region = await db.get(Region, site.region_id)
        if region:
            site.region = region.name


async def create_site(
    db: AsyncSession,
    data: SiteCreate,
    user_id: int | None = None,
) -> Site:
    history_batch_id = make_history_batch_id("web-create") if user_id is not None else None
    history_timestamp = datetime.now(timezone.utc) if history_batch_id else None
    create_data = data.model_dump(exclude_none=True)

    site = Site(**data.model_dump())
    db.add(site)
    await db.flush()
    await _sync_region_text(db, site)

    if history_batch_id:
        history_fields = [field for field in create_data.keys() if field != "site_id"]
        if "region_id" in create_data and "region" not in history_fields and site.region:
            history_fields.append("region")
        record_site_creation(
            db,
            site,
            field_names=history_fields,
            user_id=user_id,
            batch_id=history_batch_id,
            changed_at=history_timestamp,
        )

    await db.flush()
    result = await db.execute(_base_query().where(Site.id == site.id))
    return result.scalar_one()


async def update_site(
    db: AsyncSession,
    site: Site,
    data: SiteUpdate,
    user_id: int | None = None,
) -> Site:
    update_data = data.model_dump(exclude_none=True)
    history_batch_id = make_history_batch_id("web-update") if user_id is not None and update_data else None
    history_timestamp = datetime.now(timezone.utc) if history_batch_id else None
    tracked_fields = list(update_data.keys())
    if "region_id" in update_data and "region" not in tracked_fields:
        tracked_fields.append("region")
    before_values = capture_site_field_values(site, tracked_fields) if history_batch_id else {}

    for field, value in update_data.items():
        setattr(site, field, value)
    await db.flush()
    await _sync_region_text(db, site)

    if history_batch_id:
        record_site_field_changes(
            db,
            site,
            before_values,
            user_id=user_id,
            batch_id=history_batch_id,
            changed_at=history_timestamp,
        )

    await db.flush()
    result = await db.execute(_base_query().where(Site.id == site.id))
    return result.scalar_one()


async def delete_site(db: AsyncSession, site: Site) -> None:
    await db.delete(site)
    await db.flush()


async def bulk_upsert_sites(
    db: AsyncSession,
    rows: list[dict],
    project_id: int | None = None,
    user_id: int | None = None,
    history_batch_id: str | None = None,
) -> tuple[int, int, list[str]]:
    """
    Batch update из Excel.
    Возвращает (created, updated, errors).
    """
    created = updated = 0
    errors: list[str] = []
    history_batch_id = history_batch_id or (
        make_history_batch_id("excel-import") if user_id is not None else None
    )
    history_timestamp = datetime.now(timezone.utc) if history_batch_id else None

    # Загружаем все существующие site_id одним запросом
    site_ids = [r.get("site_id") for r in rows if r.get("site_id")]
    existing_map: dict[str, Site] = {}
    if site_ids:
        result = await db.execute(select(Site).where(Site.site_id.in_(site_ids)))
        for s in result.scalars().all():
            existing_map[s.site_id] = s

    # Кэш регионов по имени
    region_cache: dict[str, int] = {}

    for i, row in enumerate(rows, start=2):  # start=2 — строка Excel (с учётом заголовка)
        site_id = str(row.get("site_id", "")).strip().upper()
        if not site_id:
            errors.append(f"Строка {i}: отсутствует site_id")
            continue

        # Резолвим region_id по имени если задан регион-текст
        region_name = row.get("region")
        if region_name and region_name not in region_cache:
            from app.crud.region import get_region_by_name
            reg = await get_region_by_name(db, region_name)
            if reg:
                region_cache[region_name] = reg.id
        if region_name and region_name in region_cache:
            row["region_id"] = region_cache[region_name]

        try:
            if site_id in existing_map:
                site = existing_map[site_id]
                row["site_id"] = site_id
                row = apply_template_derivations(row, site=site)
                row.pop("site_id", None)
                if project_id is not None and site.project_id not in (None, project_id):
                    errors.append(
                        f"Строка {i} ({site_id}): объект относится к другому проекту"
                    )
                    continue
                if project_id is not None and site.project_id is None:
                    site.project_id = project_id
                update_fields = [
                    field
                    for field, value in row.items()
                    if field != "site_id" and value is not None and hasattr(site, field)
                ]
                tracked_fields = list(update_fields)
                if "region_id" in update_fields and "region" not in tracked_fields:
                    tracked_fields.append("region")
                before_values = capture_site_field_values(site, tracked_fields) if history_batch_id else {}

                for field, value in row.items():
                    if field != "site_id" and value is not None and hasattr(site, field):
                        setattr(site, field, value)

                if "region_id" in update_fields and "region" not in row:
                    await _sync_region_text(db, site)

                if history_batch_id:
                    record_site_field_changes(
                        db,
                        site,
                        before_values,
                        user_id=user_id,
                        batch_id=history_batch_id,
                        changed_at=history_timestamp,
                    )
                updated += 1
            else:
                errors.append(
                    f"Строка {i} ({site_id}): объект не найден; создание новых объектов через Excel запрещено"
                )
        except Exception as e:
            errors.append(f"Строка {i} ({site_id}): {e}")

    await db.flush()
    return created, updated, errors
