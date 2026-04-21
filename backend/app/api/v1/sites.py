from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.site import SiteCreate, SiteUpdate, SiteOut, SiteFilter, SiteListResponse
from app.crud.site import (
    get_site_by_id, get_site_by_site_id,
    get_sites, create_site, update_site, delete_site,
)
from app.crud.project import get_project_for_user
from app.crud.log import write_log
from app.api.deps import (
    get_current_user, require_admin, require_manager,
    require_contractor, require_any, get_client_ip,
)
from app.models.user import User, UserRole
from app.services.reference_sync import sync_regions_from_sites

router = APIRouter()


def _ensure_sites_module(project) -> None:
    if project.module_key != "ucn_sites_v1":
        raise HTTPException(
            status_code=400,
            detail="Sites module is not configured for this project yet",
        )


@router.get("/", response_model=SiteListResponse)
async def list_sites(
    project_id: int,
    region: str | None = None,
    region_id: int | None = None,
    status: str | None = None,
    contractor_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    project = await get_project_for_user(db, project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_sites_module(project)

    from app.models.site import SiteStatus
    filters = SiteFilter(
        project_id=project_id,
        region=region,
        region_id=region_id,
        status=SiteStatus(status) if status else None,
        contractor_id=contractor_id,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Contractor видит только объекты своей компании
    contractor_filter = current_user.contractor_id if current_user.role == UserRole.contractor else None
    total, sites = await get_sites(db, filters, contractor_id_filter=contractor_filter)

    return SiteListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=sites,
    )


@router.post("/", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_new_site(
    data: SiteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    project = await get_project_for_user(db, data.project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _ensure_sites_module(project)

    if await get_site_by_site_id(db, data.site_id):
        raise HTTPException(status_code=400, detail=f"Site '{data.site_id}' already exists")

    site = await create_site(db, data, user_id=current_user.id)
    await sync_regions_from_sites(db)
    site = await get_site_by_id(db, site.id)
    await write_log(
        db, "site_create", user_id=current_user.id, site_id=site.id,
        detail=f"Created site '{site.site_id}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return site


@router.get("/{site_id}", response_model=SiteOut)
async def get_site_detail(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    site = await get_site_by_id(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    project = await get_project_for_user(db, site.project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    _ensure_sites_module(project)

    # Contractor может видеть только объекты своей компании
    if current_user.role == UserRole.contractor and site.contractor_id != current_user.contractor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return site


@router.patch("/{site_id}", response_model=SiteOut)
async def update_existing_site(
    site_id: int,
    data: SiteUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_contractor),
):
    site = await get_site_by_id(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    project = await get_project_for_user(db, site.project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    _ensure_sites_module(project)

    # Contractor может менять только статус и даты на объектах своей компании
    if current_user.role == UserRole.contractor:
        if site.contractor_id != current_user.contractor_id:
            raise HTTPException(status_code=403, detail="Access denied")
        allowed_fields = {"status", "actual_start", "actual_end", "notes"}
        update_data = data.model_dump(exclude_none=True)
        forbidden = set(update_data.keys()) - allowed_fields
        if forbidden:
            raise HTTPException(
                status_code=403,
                detail=f"Contractor cannot update fields: {forbidden}",
            )

    old_status = site.status
    updated = await update_site(db, site, data, user_id=current_user.id)
    await sync_regions_from_sites(db)
    updated = await get_site_by_id(db, site.id)

    extra = data.model_dump(exclude_none=True)
    if old_status != updated.status:
        extra["status_changed"] = f"{old_status} → {updated.status}"

    await write_log(
        db, "site_update", user_id=current_user.id, site_id=site.id,
        detail=f"Updated site '{site.site_id}'",
        extra=extra,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return updated


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_site(
    site_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    site = await get_site_by_id(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    project = await get_project_for_user(db, site.project_id, current_user, allow_inactive=True)
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    _ensure_sites_module(project)

    site_id_str = site.site_id
    await delete_site(db, site)
    await sync_regions_from_sites(db)
    await write_log(
        db, "site_delete", user_id=current_user.id,
        detail=f"Deleted site '{site_id_str}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
