from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import get_password_hash
from app.crud.project import get_projects_by_ids


_ROLE_ASSIGNS_PROJECTS = {UserRole.manager, UserRole.viewer}


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).options(selectinload(User.projects)).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
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
