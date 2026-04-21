from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, require_admin, require_any
from app.crud.log import write_log
from app.crud.project import (
    count_project_sites,
    create_project,
    delete_project,
    get_project,
    get_project_by_code,
    get_project_by_name,
    get_project_for_user,
    get_projects_for_user,
    update_project,
)
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter()


@router.get("/", response_model=list[ProjectOut])
async def list_projects(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    return await get_projects_for_user(db, current_user, active_only=active_only)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project_detail(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    allow_inactive = current_user.role == UserRole.admin
    project = await get_project_for_user(db, project_id, current_user, allow_inactive=allow_inactive)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    data: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if await get_project_by_name(db, data.name):
        raise HTTPException(status_code=400, detail=f"Project '{data.name}' already exists")
    if await get_project_by_code(db, data.code):
        raise HTTPException(status_code=400, detail=f"Project code '{data.code}' already exists")

    project = await create_project(db, data)
    await write_log(
        db,
        "project_create",
        user_id=current_user.id,
        detail=f"Created project '{project.name}'",
        extra={"code": project.code, "module_key": project.module_key},
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_existing_project(
    project_id: int,
    data: ProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name and data.name != project.name:
        existing = await get_project_by_name(db, data.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Project '{data.name}' already exists")
    if data.code and data.code != project.code:
        existing = await get_project_by_code(db, data.code)
        if existing:
            raise HTTPException(status_code=400, detail=f"Project code '{data.code}' already exists")

    updated = await update_project(db, project, data)
    await write_log(
        db,
        "project_update",
        user_id=current_user.id,
        detail=f"Updated project '{updated.name}'",
        extra=data.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_project(
    project_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    site_count = await count_project_sites(db, project_id)
    if site_count:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a project that already contains objects",
        )

    project_name = project.name
    await delete_project(db, project)
    await write_log(
        db,
        "project_delete",
        user_id=current_user.id,
        detail=f"Deleted project '{project_name}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
