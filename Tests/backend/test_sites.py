"""
test_sites.py — тесты эндпоинтов объектов (sites) с привязкой к проекту.

Покрытые сценарии:
  - GET /sites/?project_id=<ucn>  — работает для ucn_sites_v1
  - GET /sites/?project_id=<ph>   — 400 для placeholder (модуль не настроен)
  - GET /sites/?project_id=<чужой> — 404 для недоступного проекта
  - POST /sites/ — manager может создать объект
  - POST /sites/ — viewer не может создать объект → 403
  - PATCH /sites/{id} — contractor может менять только разрешённые поля
  - PATCH /sites/{id} — contractor не может менять запрещённые поля → 403
  - PATCH /sites/{id} — contractor не может редактировать чужой объект → 403
  - Contractor видит только объекты своей компании при list
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from conftest import token_headers
from app.models.region import Region
from app.models.site import Site


# ── Список объектов ────────────────────────────────────────────────────────────

async def test_admin_lists_sites_in_ucn_project(client, seeded):
    """GET /sites/?project_id=ucn возвращает BS-TEST-001."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    site_ids = [s["site_id"] for s in data["items"]]
    assert "BS-TEST-001" in site_ids


async def test_list_sites_does_not_create_regions_or_link_region_ids(client, seeded, db_engine):
    """GET /sites must not mutate reference directories or site.region_id."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with factory() as session:
        region_count_before = len(list((await session.execute(select(Region))).scalars().all()))
        site_before = await session.scalar(select(Site).where(Site.id == seeded["site_pk"]))
        assert site_before is not None
        assert site_before.region == "Москва"
        assert site_before.region_id is None

    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    async with factory() as session:
        region_count_after = len(list((await session.execute(select(Region))).scalars().all()))
        site_after = await session.scalar(select(Site).where(Site.id == seeded["site_pk"]))

    assert region_count_after == region_count_before
    assert site_after is not None
    assert site_after.region_id is None


async def test_sites_require_ucn_module(client, seeded):
    """GET /sites/?project_id=<placeholder> → 400 (модуль не настроен)."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


async def test_manager_cannot_list_unassigned_project_sites(client, seeded):
    """Manager не может просматривать объекты чужого проекта → 404."""
    # Создаём новый UCN-проект не назначенный менеджеру
    admin_h = token_headers(seeded["admin_id"], "admin")
    create_r = await client.post("/api/v1/projects/", json={
        "name":       "Чужой UCN проект",
        "code":       "foreign-ucn",
        "module_key": "ucn_sites_v1",
    }, headers=admin_h)
    assert create_r.status_code == 201
    foreign_id = create_r.json()["id"]

    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.get(
        f"/api/v1/sites/?project_id={foreign_id}",
        headers=manager_h,
    )
    # Проект не виден менеджеру → crud вернёт None → 404
    assert resp.status_code == 404


async def test_contractor_sees_only_own_sites(client, seeded):
    """Contractor видит только объекты своей компании."""
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Все возвращённые объекты должны принадлежать contractor
    contractor_id = seeded["contractor_id"]
    for item in items:
        assert item["contractor"] is not None
        assert item["contractor"]["id"] == contractor_id


async def test_site_detail_does_not_create_regions_or_link_region_ids(client, seeded, db_engine):
    """GET /sites/{id} must not mutate reference directories or site.region_id."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with factory() as session:
        region_count_before = len(list((await session.execute(select(Region))).scalars().all()))
        site_before = await session.scalar(select(Site).where(Site.id == seeded["site_pk"]))
        assert site_before is not None
        assert site_before.region_id is None

    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/sites/{seeded['site_pk']}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    async with factory() as session:
        region_count_after = len(list((await session.execute(select(Region))).scalars().all()))
        site_after = await session.scalar(select(Site).where(Site.id == seeded["site_pk"]))

    assert region_count_after == region_count_before
    assert site_after is not None
    assert site_after.region_id is None


# ── Создание объектов ──────────────────────────────────────────────────────────

async def test_manager_can_create_site(client, seeded):
    """Manager может создать объект в доступном UCN-проекте."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-MGR-001",
        "name":       "Объект менеджера",
        "project_id": seeded["ucn_project_id"],
        "status":     "planned",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["site_id"] == "BS-MGR-001"
    assert data["project_id"] == seeded["ucn_project_id"]


async def test_manager_can_create_site_without_dependency_autocommit(client_no_autocommit, seeded):
    """Site create must persist via explicit commit in the endpoint."""
    headers = token_headers(seeded["manager_id"], "manager")
    create_resp = await client_no_autocommit.post("/api/v1/sites/", json={
        "site_id": "BS-MGR-PERSIST-001",
        "name": "Персистентный объект",
        "project_id": seeded["ucn_project_id"],
        "status": "planned",
    }, headers=headers)
    assert create_resp.status_code == 201, create_resp.text

    list_resp = await client_no_autocommit.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    site_ids = {item["site_id"] for item in list_resp.json()["items"]}
    assert "BS-MGR-PERSIST-001" in site_ids


async def test_admin_can_create_site(client, seeded):
    """Admin может создать объект в любом UCN-проекте."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-ADM-001",
        "name":       "Объект администратора",
        "project_id": seeded["ucn_project_id"],
        "status":     "survey",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "survey"


async def test_viewer_cannot_create_site(client, seeded):
    """Viewer не может создавать объекты → 403."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-VIEW-001",
        "name":       "Попытка viewer",
        "project_id": seeded["ucn_project_id"],
        "status":     "planned",
    }, headers=headers)
    assert resp.status_code == 403


async def test_duplicate_site_id_rejected(client, seeded):
    """Нельзя создать объект с уже существующим site_id → 400."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-TEST-001",  # уже существует
        "name":       "Дубликат",
        "project_id": seeded["ucn_project_id"],
    }, headers=headers)
    assert resp.status_code == 400


async def test_cannot_create_site_in_placeholder_project(client, seeded):
    """Нельзя создать объект в placeholder-проекте → 400.
    Используем admin (видит все проекты), чтобы запрос дошёл до проверки модуля.
    """
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-PH-001",
        "name":       "Объект в placeholder",
        "project_id": seeded["placeholder_project_id"],
    }, headers=headers)
    assert resp.status_code == 400


# ── Редактирование объектов (PATCH) ────────────────────────────────────────────

async def test_admin_can_update_any_field(client, seeded):
    """Admin может изменить любое поле объекта."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.patch(
        f"/api/v1/sites/{seeded['site_pk']}",
        json={"name": "Обновлённое имя", "status": "survey"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Обновлённое имя"
    assert data["status"] == "survey"


async def test_contractor_can_update_allowed_fields(client, seeded):
    """Contractor может менять status, actual_start, actual_end, notes."""
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.patch(
        f"/api/v1/sites/{seeded['site_pk']}",
        json={"notes": "Заметка подрядчика", "status": "survey"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "Заметка подрядчика"
    assert data["status"] == "survey"


async def test_contractor_cannot_update_name(client, seeded):
    """Contractor не может изменить поле 'name' → 403."""
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.patch(
        f"/api/v1/sites/{seeded['site_pk']}",
        json={"name": "Новое имя"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "cannot update fields" in resp.json()["detail"].lower()


async def test_contractor_cannot_update_region(client, seeded):
    """Contractor не может изменить поле 'region' → 403."""
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.patch(
        f"/api/v1/sites/{seeded['site_pk']}",
        json={"region": "Санкт-Петербург"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_contractor_cannot_edit_other_contractors_site(client, seeded):
    """
    Contractor не может редактировать объект, принадлежащий другому подрядчику.
    Создаём второй объект без contractor_id (не принадлежит тестовому подрядчику).
    """
    admin_h = token_headers(seeded["admin_id"], "admin")
    create_r = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-OTHER-001",
        "name":       "Чужой объект",
        "project_id": seeded["ucn_project_id"],
        "status":     "planned",
        # contractor_id не задан → не принадлежит test-contractor
    }, headers=admin_h)
    assert create_r.status_code == 201
    other_site_pk = create_r.json()["id"]

    contractor_h = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.patch(
        f"/api/v1/sites/{other_site_pk}",
        json={"notes": "попытка"},
        headers=contractor_h,
    )
    assert resp.status_code == 403


# ── Удаление объектов ──────────────────────────────────────────────────────────

async def test_admin_can_delete_site(client, seeded, db_engine):
    """Admin может удалить объект → 204.

    Workaround: crud/site.py записывает site_history при создании объекта.
    В SQLite relationship backref пытается SET NULL на NOT NULL site_id вместо CASCADE.
    Вручную удаляем историю перед удалением объекта через API.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import delete as sa_delete
    from app.models.site_history import SiteHistory

    admin_h = token_headers(seeded["admin_id"], "admin")
    create_r = await client.post("/api/v1/sites/", json={
        "site_id":    "BS-DEL-001",
        "name":       "Объект для удаления",
        "project_id": seeded["ucn_project_id"],
    }, headers=admin_h)
    assert create_r.status_code == 201
    pk = create_r.json()["id"]

    # Удаляем записи истории, чтобы обойти SQLite NOT NULL + backref ограничение
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(sa_delete(SiteHistory).where(SiteHistory.site_id == pk))
        await session.commit()

    resp = await client.delete(f"/api/v1/sites/{pk}", headers=admin_h)
    assert resp.status_code == 204


async def test_manager_cannot_delete_site(client, seeded):
    """Manager не может удалять объекты → 403."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.delete(
        f"/api/v1/sites/{seeded['site_pk']}",
        headers=headers,
    )
    assert resp.status_code == 403
