from dataclasses import dataclass

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import TokenData
from app.services.auth import ACCESS_TOKEN_TYPE, EXCEL_SYNC_TOKEN_TYPE, decode_token
from app.crud.user import get_user_by_id
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer()


@dataclass(frozen=True)
class AuthContext:
    user: User
    token_data: TokenData


def get_token_data(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    token_data = decode_token(credentials.credentials)
    if not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return token_data


async def _get_active_user(
    token_data: TokenData,
    db: AsyncSession,
    *,
    allowed_token_types: set[str],
) -> User:
    if token_data.token_type not in allowed_token_types:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = await get_user_by_id(db, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user(
    token_data: TokenData = Depends(get_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _get_active_user(
        token_data,
        db,
        allowed_token_types={ACCESS_TOKEN_TYPE},
    )


async def get_sync_auth_context(
    token_data: TokenData = Depends(get_token_data),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    user = await _get_active_user(
        token_data,
        db,
        allowed_token_types={ACCESS_TOKEN_TYPE, EXCEL_SYNC_TOKEN_TYPE},
    )
    if user.role not in {UserRole.admin, UserRole.manager}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required roles: {[UserRole.admin.value, UserRole.manager.value]}",
        )
    return AuthContext(user=user, token_data=token_data)


async def get_sync_columns_context(
    token_data: TokenData = Depends(get_token_data),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    user = await _get_active_user(
        token_data,
        db,
        allowed_token_types={ACCESS_TOKEN_TYPE, EXCEL_SYNC_TOKEN_TYPE},
    )
    return AuthContext(user=user, token_data=token_data)


def require_roles(*roles: UserRole):
    """Фабрика зависимостей для проверки ролей."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# Shortcut-зависимости
require_admin = require_roles(UserRole.admin)
require_manager = require_roles(UserRole.admin, UserRole.manager)
require_contractor = require_roles(UserRole.admin, UserRole.manager, UserRole.contractor)
require_any = require_roles(*UserRole)  # все авторизованные


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
