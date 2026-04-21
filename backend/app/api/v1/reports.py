from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_any
from app.crud.project import get_project_for_user
from app.crud.site import get_all_sites_for_export
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.report import ProjectReportOut, ReportDefinitionOut
from app.services.reports import build_project_report, get_report_definitions

router = APIRouter()


@router.get("/", response_model=list[ReportDefinitionOut])
async def list_project_reports(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    project = await get_project_for_user(
        db,
        project_id,
        current_user,
        allow_inactive=current_user.role == UserRole.admin,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_report_definitions(project)


@router.get("/{report_key}", response_model=ProjectReportOut)
async def get_project_report(
    report_key: str,
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    project = await get_project_for_user(
        db,
        project_id,
        current_user,
        allow_inactive=current_user.role == UserRole.admin,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    contractor_filter = current_user.contractor_id if current_user.role == UserRole.contractor else None
    if current_user.role == UserRole.contractor and contractor_filter is None:
        sites = []
    else:
        sites = await get_all_sites_for_export(
            db,
            project_id=project.id,
            contractor_id_filter=contractor_filter,
        )

    try:
        return build_project_report(project, report_key, sites)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found for this project") from exc
