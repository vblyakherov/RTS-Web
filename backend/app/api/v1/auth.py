from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserMe, UserSelfUpdate, UserUpdate
from app.crud.user import get_user_by_username, update_user
from app.crud.log import write_log
from app.services.auth import verify_password, create_access_token
from app.api.deps import get_current_user, get_client_ip
from app.models.user import User
from app.limiter import limiter

router = APIRouter()


def _sanitize_self_update_extra(extra: dict) -> dict | None:
    if not extra:
        return None
    safe_extra = {k: v for k, v in extra.items() if k != "password"}
    if "password" in extra:
        safe_extra["password_changed"] = True
    return safe_extra or None


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(user.id, user.role.value)

    await write_log(
        db,
        action="login",
        user_id=user.id,
        detail=f"User '{user.username}' logged in",
        ip_address=get_client_ip(request),
    )
    await db.commit()

    return Token(access_token=token)


@router.get("/me", response_model=UserMe)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserMe)
async def update_me(
    data: UserSelfUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    new_username = payload.get("username")
    if new_username is not None and new_username != current_user.username:
        existing = await get_user_by_username(db, new_username)
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

    old_username = current_user.username
    updated = await update_user(db, current_user, UserUpdate(**payload))
    detail = (
        f"Updated own credentials '{old_username}' -> '{updated.username}'"
        if updated.username != old_username
        else f"Updated own credentials for '{updated.username}'"
    )
    await write_log(
        db,
        action="user_update",
        user_id=current_user.id,
        detail=detail,
        extra=_sanitize_self_update_extra(payload),
        ip_address=get_client_ip(request),
    )
    await db.commit()

    return updated
