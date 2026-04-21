from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.database import get_db
from app.crud.site import get_all_sites_for_export, bulk_upsert_sites
from app.crud.project import get_project_for_user
from app.crud.site_history import make_history_batch_id
from app.crud.log import write_log
from app.services.excel import ExcelTemplateError, export_sites_to_excel, parse_excel_import
from app.services.auth import EXCEL_SYNC_TOKEN_TYPE, create_access_token
from app.api.deps import require_manager, require_any, get_client_ip
from app.models.user import User, UserRole
from app.config import settings
from app.services.reference_sync import sync_regions_from_sites

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.get("/export")
async def export_excel(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
    request: Request = None,
):
    """Экспорт всех объектов в Excel. Contractor видит только свои."""
    project = await get_project_for_user(db, project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.module_key != "ucn_sites_v1":
        raise HTTPException(status_code=400, detail="Excel export is not configured for this project yet")

    contractor_filter = current_user.contractor_id if current_user.role == UserRole.contractor else None
    sites = await get_all_sites_for_export(
        db,
        project_id=project_id,
        contractor_id_filter=contractor_filter,
    )
    excel_token = create_access_token(
        current_user.id,
        current_user.role.value,
        expires_delta=timedelta(minutes=settings.EXCEL_EXPORT_TOKEN_EXPIRE_MINUTES),
        token_type=EXCEL_SYNC_TOKEN_TYPE,
        project_id=project_id,
        contractor_id=current_user.contractor_id,
    )

    try:
        xlsm_bytes = export_sites_to_excel(
            sites,
            auth_token=excel_token,
            username=current_user.username,
            project_id=project_id,
        )
    except ExcelTemplateError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{project.code}_sites_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsm"

    await write_log(
        db, "excel_export",
        user_id=current_user.id,
        detail=f"Exported {len(sites)} sites from project '{project.name}'",
        extra={"project_id": project.id, "project_code": project.code},
        ip_address=get_client_ip(request) if request else None,
    )
    await db.commit()

    return Response(
        content=xlsm_bytes,
        media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_excel(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
    request: Request = None,
):
    """Импорт объектов из Excel. Только admin и manager."""
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xlsm files are supported")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    project = await get_project_for_user(db, project_id, current_user, allow_inactive=current_user.role == UserRole.admin)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.module_key != "ucn_sites_v1":
        raise HTTPException(status_code=400, detail="Excel import is not configured for this project yet")

    # Парсинг
    rows, parse_errors = parse_excel_import(raw)

    if not rows and parse_errors:
        raise HTTPException(status_code=422, detail={"parse_errors": parse_errors})

    # Bulk upsert
    history_batch_id = make_history_batch_id("excel-import")
    created, updated, upsert_errors = await bulk_upsert_sites(
        db,
        rows,
        project_id=project_id,
        user_id=current_user.id,
        history_batch_id=history_batch_id,
    )
    await sync_regions_from_sites(db)

    all_errors = parse_errors + upsert_errors

    await write_log(
        db, "excel_import",
        user_id=current_user.id,
        detail=f"Import: created={created}, updated={updated}, errors={len(all_errors)}",
        extra={
            "filename": file.filename,
            "created": created,
            "updated": updated,
            "project_id": project.id,
            "project_code": project.code,
            "history_batch_id": history_batch_id,
            "errors": all_errors[:50],  # Сохраняем первые 50 ошибок
        },
        ip_address=get_client_ip(request) if request else None,
    )
    await db.commit()

    return {
        "success": True,
        "created": created,
        "updated": updated,
        "total_processed": created + updated,
        "errors_count": len(all_errors),
        "errors": all_errors,
    }
