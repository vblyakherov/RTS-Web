"""
test_projects.py — тесты RBAC для проектов (двухуровневая архитектура).

Покрытые сценарии:
  - GET /projects/ — admin видит ВСЕ проекты (ucn + placeholder)
  - GET /projects/ — manager видит ТОЛЬКО назначенные проекты (ucn, не placeholder)
  - GET /projects/ — viewer видит ТОЛЬКО назначенные проекты
  - GET /projects/ — contractor видит проекты через объекты своего подрядчика
  - POST /projects/ — только admin; manager/viewer → 403
  - DELETE /projects/{id} — нельзя удалить проект с объектами → 400
  - DELETE /projects/{id} — можно удалить пустой placeholder-проект → 204
  - is_configured отражает module_key (ucn_sites_v1 = True, placeholder = False)
"""
import pytest
from conftest import token_headers


# ── Список проектов по ролям ───────────────────────────────────────────────────

async def test_admin_sees_all_projects(client, seeded):
    """Admin видит все активные проекты (ucn и placeholder)."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get("/api/v1/projects/", headers=headers)
    assert resp.status_code == 200
    project_ids = {p["id"] for p in resp.json()}
    assert seeded["ucn_project_id"]         in project_ids
    assert seeded["placeholder_project_id"] in project_ids


async def test_manager_sees_only_assigned_projects(client, seeded):
    """Manager видит только UCN-проект (назначен), но не placeholder."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.get("/api/v1/projects/", headers=headers)
    assert resp.status_code == 200
    project_ids = {p["id"] for p in resp.json()}
    assert seeded["ucn_project_id"]         in project_ids
    assert seeded["placeholder_project_id"] not in project_ids


async def test_viewer_sees_only_assigned_projects(client, seeded):
    """Viewer видит только назначенный UCN-проект."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.get("/api/v1/projects/", headers=headers)
    assert resp.status_code == 200
    project_ids = {p["id"] for p in resp.json()}
    assert seeded["ucn_project_id"]         in project_ids
    assert seeded["placeholder_project_id"] not in project_ids


async def test_contractor_sees_projects_via_sites(client, seeded):
    """
    Contractor видит проекты, где его подрядчик привязан к объектам.
    BS-TEST-001 → ucn-проект → contractor_user должен видеть ucn.
    """
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.get("/api/v1/projects/", headers=headers)
    assert resp.status_code == 200
    project_ids = {p["id"] for p in resp.json()}
    assert seeded["ucn_project_id"] in project_ids


async def test_contractor_with_no_sites_sees_no_projects(client, seeded, db_engine):
    """
    Contractor без объектов не видит ни одного проекта.
    Создаём нового contractor-пользователя без объектов и проверяем пустой список.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.user import User, UserRole
    from app.models.contractor import Contractor
    from app.services.auth import get_password_hash

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        new_contractor = Contractor(name="Нет объектов ООО")
        session.add(new_contractor)
        await session.flush()

        empty_user = User(
            username="t_empty_contractor",
            email="empty@test.local",
            hashed_password=get_password_hash("Empty1234"),
            role=UserRole.contractor,
            is_active=True,
            contractor_id=new_contractor.id,
        )
        session.add(empty_user)
        await session.flush()
        empty_user_id = empty_user.id
        await session.commit()

    headers = token_headers(empty_user_id, "contractor")
    resp = await client.get("/api/v1/projects/", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == [], f"Ожидали пустой список, получили: {resp.json()}"


# ── Создание проектов ──────────────────────────────────────────────────────────

async def test_admin_can_create_project(client, seeded):
    """Admin может создать новый проект."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/projects/", json={
        "name":       "Тест Создание",
        "code":       "test-create",
        "module_key": "placeholder",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "test-create"
    assert data["is_configured"] is False


async def test_admin_can_create_project_without_dependency_autocommit(client_no_autocommit, seeded):
    """Project create must persist via explicit commit in the endpoint."""
    headers = token_headers(seeded["admin_id"], "admin")
    create_resp = await client_no_autocommit.post("/api/v1/projects/", json={
        "name": "Персистентный проект",
        "code": "persisted-project",
        "module_key": "placeholder",
    }, headers=headers)
    assert create_resp.status_code == 201, create_resp.text

    list_resp = await client_no_autocommit.get(
        "/api/v1/projects/?active_only=false",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    codes = {item["code"] for item in list_resp.json()}
    assert "persisted-project" in codes


async def test_admin_creates_ucn_project_is_configured(client, seeded):
    """Проект с module_key=ucn_sites_v1 отдаёт is_configured=True."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/projects/", json={
        "name":       "Тест UCN настроен",
        "code":       "test-ucn-cfg",
        "module_key": "ucn_sites_v1",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["is_configured"] is True


async def test_manager_cannot_create_project(client, seeded):
    """Manager не может создавать проекты → 403."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/projects/", json={
        "name": "Запрещённый проект",
        "code": "forbidden-proj",
    }, headers=headers)
    assert resp.status_code == 403


async def test_viewer_cannot_create_project(client, seeded):
    """Viewer не может создавать проекты → 403."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.post("/api/v1/projects/", json={
        "name": "Запрещённый проект",
        "code": "viewer-forbidden",
    }, headers=headers)
    assert resp.status_code == 403


async def test_duplicate_project_code_rejected(client, seeded):
    """Попытка создать проект с существующим кодом → 400."""
    headers = token_headers(seeded["admin_id"], "admin")
    # ucn-2026 уже существует
    resp = await client.post("/api/v1/projects/", json={
        "name": "Другое название",
        "code": "ucn-2026",
    }, headers=headers)
    assert resp.status_code == 400


# ── Удаление проектов ──────────────────────────────────────────────────────────

async def test_cannot_delete_project_with_sites(client, seeded):
    """
    Нельзя удалить проект, в котором есть объекты.
    UCN-проект содержит BS-TEST-001.
    """
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.delete(
        f"/api/v1/projects/{seeded['ucn_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "objects" in resp.json()["detail"]


async def test_can_delete_empty_project(client, seeded):
    """Пустой placeholder-проект можно удалить → 204."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.delete(
        f"/api/v1/projects/{seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 204

    # Убедиться, что проект больше не виден
    get_resp = await client.get(
        f"/api/v1/projects/{seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert get_resp.status_code == 404


async def test_manager_cannot_delete_project(client, seeded):
    """Manager не может удалять проекты → 403."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.delete(
        f"/api/v1/projects/{seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 403


# ── is_configured флаг ────────────────────────────────────────────────────────

async def test_ucn_project_is_configured(client, seeded):
    """UCN-проект: is_configured=True (module_key=ucn_sites_v1)."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/projects/{seeded['ucn_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_configured"] is True
    assert resp.json()["module_key"] == "ucn_sites_v1"


async def test_placeholder_project_is_not_configured(client, seeded):
    """Placeholder-проект: is_configured=False."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/projects/{seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_configured"] is False
    assert resp.json()["module_key"] == "placeholder"
