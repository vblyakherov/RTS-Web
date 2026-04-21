from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.crud.user import (
    get_user_by_id, get_user_by_username, get_user_by_email,
    get_users, create_user, update_user, delete_user,
)
from app.crud.project import get_projects_by_ids
from app.crud.log import write_log
from app.api.deps import require_admin, get_current_user, get_client_ip
from app.models.user import User, UserRole

router = APIRouter()


def _sanitize_user_update_extra(extra: dict) -> dict | None:
    if not extra:
        return None
    safe_extra = {k: v for k, v in extra.items() if k != "password"}
    if "password" in extra:
        safe_extra["password_changed"] = True
    return safe_extra or None


async def _validate_unique_user_fields(
    db: AsyncSession,
    user: User,
    username: str | None = None,
    email: str | None = None,
) -> None:
    if username is not None and username != user.username:
        existing = await get_user_by_username(db, username)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Username already exists")

    if email is not None and email != user.email:
        existing = await get_user_by_email(db, email)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Email already exists")


async def _validate_project_ids(db: AsyncSession, project_ids: list[int] | None) -> None:
    if not project_ids:
        return
    unique_ids = sorted(set(project_ids))
    existing = await get_projects_by_ids(db, unique_ids)
    existing_ids = {project.id for project in existing}
    missing_ids = [project_id for project_id in unique_ids if project_id not in existing_ids]
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown project ids: {missing_ids}",
        )


@router.get("/", response_model=list[UserOut])
async def list_users(
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    _, users = await get_users(db, role=role, is_active=is_active, page=page, page_size=page_size)
    return users


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await _validate_project_ids(db, data.project_ids)

    if await get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if await get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already exists")

    user = await create_user(db, data)
    await write_log(
        db, "user_create", user_id=current_user.id,
        detail=f"Created user '{user.username}' with role '{user.role}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_existing_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await _validate_unique_user_fields(db, user, username=data.username, email=data.email)
    await _validate_project_ids(db, data.project_ids)

    old_username = user.username
    updated = await update_user(db, user, data)
    log_extra = _sanitize_user_update_extra(data.model_dump(exclude_unset=True))
    username_detail = (
        f"Updated user '{old_username}' -> '{updated.username}'"
        if updated.username != old_username
        else f"Updated user '{updated.username}'"
    )
    await write_log(
        db, "user_update", user_id=current_user.id,
        detail=username_detail,
        extra=log_extra,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    username = user.username
    await delete_user(db, user)
    await write_log(
        db, "user_delete", user_id=current_user.id,
        detail=f"Deleted user '{username}'",
        ip_address=get_client_ip(request),
    )
    await db.commit()
