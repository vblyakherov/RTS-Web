"""
conftest.py — общие фикстуры для backend-тестов RTKS Tracker.

Стратегия базы данных:
  - Каждый тест получает свежую in-memory SQLite БД (function scope).
  - Схема создаётся через Base.metadata.create_all — без Alembic.
  - get_db dependency переопределяется через app.dependency_overrides.
  - Аутентификация: JWT-токены формируются прямым вызовом create_access_token,
    без обращения к /auth/login.

Ограничения SQLite vs PostgreSQL:
  - Enum-типы с именами (name="user_role") работают как VARCHAR — ОК.
  - DateTime(timezone=True) хранится как text — ОК для большинства сравнений.
  - onupdate=func.now() НЕ срабатывает автоматически — updated_at не обновляется
    при UPDATE в тестах, если не задан явно. Это допустимо для наших тестов.
  - FK-ограничения SQLite не принудительны по умолчанию (нам это не мешает).
"""
import os
import sys
from pathlib import Path

# ── Переменные окружения нужно задать ДО любого импорта app-кода ──────────────
#
# Используем фейковый PostgreSQL URL, чтобы database.py мог создать движок
# с pool_size/max_overflow (эти параметры валидны только для PostgreSQL/QueuePool,
# но не для SQLite/StaticPool).
# Реальные тесты используют SQLite через override get_db — к PostgreSQL
# соединений не будет.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/tracker_test_fake",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-min32-characters-ok!")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")

# ── Добавить backend/ в sys.path ───────────────────────────────────────────────
_backend = str(Path(__file__).resolve().parents[2] / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# ── Импорты ───────────────────────────────────────────────────────────────────
import pytest
from sqlalchemy import event
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.user import User, UserRole
from app.models.project import Project, user_projects
from app.models.site import Site, SiteStatus
from app.models.contractor import Contractor
from app.services.auth import get_password_hash, create_access_token


# ── Вспомогательная функция: заголовки авторизации ────────────────────────────

def token_headers(user_id: int, role: str, **token_kwargs) -> dict:
    """Генерирует Bearer-заголовок для данного user_id/role."""
    token = create_access_token(user_id, role, **token_kwargs)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_limiter_storage():
    """
    SlowAPI rate-limit storage is process-global.

    Without a reset between tests, multiple login assertions in one pytest run
    start to hit the shared 5/minute bucket and mask unrelated failures.
    """
    storage = getattr(app.state.limiter, "_storage", None)
    if storage and hasattr(storage, "reset"):
        storage.reset()
    yield
    if storage and hasattr(storage, "reset"):
        storage.reset()


# ── Фикстура: движок in-memory SQLite (function scope = свежая БД каждый тест) ─

@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


# ── Фикстура: начальные данные ─────────────────────────────────────────────────

@pytest.fixture
async def seeded(db_engine):
    """
    Наполняет тестовую БД базовым набором:
      - 1 подрядчик (ООО Тест-Строй)
      - 4 пользователя: admin, manager, viewer, contractor_user
      - 2 проекта: ucn (ucn_sites_v1) и placeholder (placeholder)
      - manager и viewer назначены на ucn-проект
      - 1 объект (BS-TEST-001) в ucn-проекте, принадлежит подрядчику

    Возвращает dict с id всех созданных сущностей.
    """
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        # Подрядчик
        contractor = Contractor(name="ООО Тест-Строй")
        session.add(contractor)
        await session.flush()

        # Пользователи
        admin = User(
            username="t_admin", email="admin@test.local",
            hashed_password=get_password_hash("Admin1234"),
            role=UserRole.admin, is_active=True,
        )
        manager = User(
            username="t_manager", email="manager@test.local",
            hashed_password=get_password_hash("Mgr1234"),
            role=UserRole.manager, is_active=True,
        )
        viewer = User(
            username="t_viewer", email="viewer@test.local",
            hashed_password=get_password_hash("View1234"),
            role=UserRole.viewer, is_active=True,
        )
        cuser = User(
            username="t_contractor", email="cuser@test.local",
            hashed_password=get_password_hash("Ctr1234"),
            role=UserRole.contractor, is_active=True,
        )
        for u in [admin, manager, viewer, cuser]:
            session.add(u)
        await session.flush()

        cuser.contractor_id = contractor.id

        # Проекты
        ucn = Project(
            name="УЦН 2.0 2026 год",
            code="ucn-2026",
            description="Тест UCN",
            module_key="ucn_sites_v1",
            is_active=True,
            sort_order=10,
        )
        ph = Project(
            name="ТСПУ",
            code="tspu",
            description="Тест Placeholder",
            module_key="placeholder",
            is_active=True,
            sort_order=20,
        )
        session.add(ucn)
        session.add(ph)
        await session.flush()

        # Назначить manager и viewer на UCN-проект
        await session.execute(
            user_projects.insert().values([
                {"user_id": manager.id, "project_id": ucn.id},
                {"user_id": viewer.id,   "project_id": ucn.id},
            ])
        )

        # Объект, принадлежащий подрядчику
        site = Site(
            site_id="BS-TEST-001",
            name="Тестовый объект 001",
            project_id=ucn.id,
            region="Москва",
            status=SiteStatus.planned,
            contractor_id=contractor.id,
        )
        session.add(site)
        await session.flush()

        await session.commit()

        return {
            "admin_id":              admin.id,
            "manager_id":            manager.id,
            "viewer_id":             viewer.id,
            "contractor_user_id":    cuser.id,
            "contractor_id":         contractor.id,
            "ucn_project_id":        ucn.id,
            "placeholder_project_id": ph.id,
            "site_pk":               site.id,
            "site_site_id":          site.site_id,
        }


# ── Фикстура: HTTP-клиент с переопределённой зависимостью get_db ───────────────

@pytest.fixture
async def client(db_engine, seeded):
    """
    AsyncClient, привязанный к тестовому движку.
    seeded включён в зависимости, чтобы данные были вставлены до первого запроса.
    """
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _test_get_db():
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _test_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client_no_autocommit(db_engine, seeded):
    """
    AsyncClient с get_db override без скрытого commit после успешного запроса.

    Нужен для тестов, которые проверяют, что write-endpoints коммитят изменения
    явно, а не полагаются на commit внутри dependency.
    """
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _test_get_db():
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.rollback()

    app.dependency_overrides[get_db] = _test_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
