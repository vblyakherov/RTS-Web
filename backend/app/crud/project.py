from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, user_projects
from app.models.site import Site
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectUpdate


def _project_stats_subqueries():
    site_counts = (
        select(
            Site.project_id.label("project_id"),
            func.count(Site.id).label("site_count"),
        )
        .group_by(Site.project_id)
        .subquery()
    )
    user_counts = (
        select(
            user_projects.c.project_id.label("project_id"),
            func.count(user_projects.c.user_id).label("assigned_user_count"),
        )
        .group_by(user_projects.c.project_id)
        .subquery()
    )
    return site_counts, user_counts


def _project_query_with_stats():
    site_counts, user_counts = _project_stats_subqueries()
    return (
        select(
            Project,
            func.coalesce(site_counts.c.site_count, 0).label("site_count"),
            func.coalesce(user_counts.c.assigned_user_count, 0).label("assigned_user_count"),
        )
        .outerjoin(site_counts, site_counts.c.project_id == Project.id)
        .outerjoin(user_counts, user_counts.c.project_id == Project.id)
    )


def _attach_project_stats(rows) -> list[Project]:
    projects: list[Project] = []
    for project, site_count, assigned_user_count in rows:
        project.site_count = site_count
        project.assigned_user_count = assigned_user_count
        projects.append(project)
    return projects


async def get_project(db: AsyncSession, project_id: int) -> Project | None:
    rows = await db.execute(_project_query_with_stats().where(Project.id == project_id))
    projects = _attach_project_stats(rows.all())
    return projects[0] if projects else None


async def get_project_by_name(db: AsyncSession, name: str) -> Project | None:
    result = await db.execute(select(Project).where(Project.name == name))
    return result.scalar_one_or_none()


async def get_project_by_code(db: AsyncSession, code: str) -> Project | None:
    result = await db.execute(select(Project).where(Project.code == code))
    return result.scalar_one_or_none()


async def get_projects_by_ids(db: AsyncSession, project_ids: list[int]) -> list[Project]:
    if not project_ids:
        return []
    result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
    return list(result.scalars().all())


async def get_projects_for_user(
    db: AsyncSession,
    current_user: User,
    active_only: bool = True,
) -> list[Project]:
    query = _project_query_with_stats()

    if active_only:
        query = query.where(Project.is_active.is_(True))

    if current_user.role == UserRole.admin:
        pass
    elif current_user.role == UserRole.contractor:
        if not current_user.contractor_id:
            return []
        accessible_project_ids = (
            select(Site.project_id)
            .where(
                Site.project_id.is_not(None),
                Site.contractor_id == current_user.contractor_id,
            )
            .distinct()
        )
        query = query.where(Project.id.in_(accessible_project_ids))
    else:
        query = (
            query.join(user_projects, user_projects.c.project_id == Project.id)
            .where(user_projects.c.user_id == current_user.id)
        )

    rows = await db.execute(query.order_by(Project.sort_order.asc(), Project.name.asc()))
    return _attach_project_stats(rows.all())


async def get_project_for_user(
    db: AsyncSession,
    project_id: int,
    current_user: User,
    allow_inactive: bool = False,
) -> Project | None:
    projects = await get_projects_for_user(db, current_user, active_only=not allow_inactive)
    for project in projects:
        if project.id == project_id:
            return project
    return None


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    project.site_count = 0
    project.assigned_user_count = 0
    return project


async def update_project(db: AsyncSession, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return await get_project(db, project.id)


async def delete_project(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.flush()


async def count_project_sites(db: AsyncSession, project_id: int) -> int:
    result = await db.execute(select(func.count(Site.id)).where(Site.project_id == project_id))
    return result.scalar_one()
