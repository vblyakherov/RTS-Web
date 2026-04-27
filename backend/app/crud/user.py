import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.config import settings
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import get_password_hash
from app.services.ldap_auth import LdapAuthenticatedUser
from app.crud.project import get_projects_by_ids


_ROLE_ASSIGNS_PROJECTS = {UserRole.manager, UserRole.viewer}


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).options(selectinload(User.projects)).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.projects)).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[int, list[User]]:
    query = select(User).options(selectinload(User.projects))
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    users = (await db.execute(query.offset(offset).limit(page_size))).scalars().all()
    return total, list(users)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        contractor_id=data.contractor_id,
    )
    db.add(user)
    await db.flush()
    if data.role in _ROLE_ASSIGNS_PROJECTS and data.project_ids:
        user.projects = await get_projects_by_ids(db, data.project_ids)
        await db.flush()
    return await get_user_by_id(db, user.id)


def _ldap_fallback_email(username: str) -> str:
    domain = settings.LDAP_DEFAULT_EMAIL_DOMAIN.strip() or "ldap.local"
    return f"{username}@{domain}"


async def _available_ldap_email(
    db: AsyncSession,
    username: str,
    ldap_email: str | None,
    current_user_id: int | None = None,
) -> str:
    candidates = []
    if ldap_email:
        candidates.append(ldap_email)
    candidates.append(_ldap_fallback_email(username))

    for candidate in candidates:
        existing = await get_user_by_email(db, candidate)
        if not existing or existing.id == current_user_id:
            return candidate

    return _ldap_fallback_email(f"{username}.{secrets.token_hex(4)}")


async def upsert_ldap_user(db: AsyncSession, data: LdapAuthenticatedUser) -> User:
    username = data.username.strip()
    user = await get_user_by_username(db, username)

    if user:
        user.email = await _available_ldap_email(
            db,
            username,
            data.email,
            current_user_id=user.id,
        )
        user.full_name = data.full_name or user.full_name
        if user.role != data.role:
            user.role = data.role
            if data.role not in _ROLE_ASSIGNS_PROJECTS:
                user.projects = []
        await db.flush()
        return await get_user_by_id(db, user.id)

    user = User(
        username=username,
        email=await _available_ldap_email(db, username, data.email),
        hashed_password=get_password_hash(secrets.token_urlsafe(32)),
        full_name=data.full_name,
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return await get_user_by_id(db, user.id)


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    update_data = data.model_dump(exclude_unset=True)
    project_ids = update_data.pop("project_ids", None)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    target_role = update_data.get("role", user.role)
    if project_ids is not None:
        user.projects = await get_projects_by_ids(db, project_ids) if target_role in _ROLE_ASSIGNS_PROJECTS else []
    elif target_role not in _ROLE_ASSIGNS_PROJECTS:
        user.projects = []

    await db.flush()
    return await get_user_by_id(db, user.id)


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()
