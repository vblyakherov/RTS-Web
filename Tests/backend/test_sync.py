"""
test_sync.py — тесты синхронизации, истории изменений и rollback.

Покрытые сценарии:
  - POST /sync — успешная синхронизация записывает NI-поле и историю
  - POST /sync — viewer/contractor не могут делать sync (require_manager)
  - GET /sync/history/{site_id} — менеджер видит историю объекта
  - GET /sync/history/{site_id} — viewer не может → 403
  - POST /sync/rollback-entry — admin откатывает изменение поля
  - POST /sync/rollback-entry — manager не может → 403
  - GET /sync/columns — возвращает список колонок для VBA

Используемое поле нового шаблона для тестов: `macroregion` (Макрорегион, str).
  - macroregion присутствует в SITE_COLUMNS.
  - Синхронизация обновляет только поля из SITE_COLUMNS (_UPDATABLE_FIELDS).
"""
import pytest
from conftest import token_headers


# ── POST /sync — успешная синхронизация ───────────────────────────────────────

async def test_sync_applies_changes_and_records_history(client, seeded):
    """
    Sync с изменённым полем macroregion:
      - applied == 1
      - в site_history появляется запись для field_name=macroregion
    """
    manager_h = token_headers(seeded["manager_id"], "manager")

    resp = await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [{
            "site_id":     "BS-TEST-001",
            "macroregion": "Дальний Восток",
        }],
        "client_version": 1,
    }, headers=manager_h)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["applied"] == 1
    assert data["errors"] == []

    # Проверить историю
    hist_resp = await client.get(
        f"/api/v1/sync/history/{seeded['site_pk']}",
        headers=manager_h,
    )
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["total"] >= 1
    field_names = [e["field_name"] for e in hist["items"]]
    assert "macroregion" in field_names, (
        f"Ожидали history-запись macroregion, получили: {field_names}"
    )


async def test_sync_without_rows_returns_all_sites(client, seeded):
    """
    Sync с пустым rows (download-only): applied == 0, rows содержит данные.
    """
    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [],
        "client_version": 1,
    }, headers=manager_h)

    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] == 0
    assert len(data["rows"]) >= 1  # BS-TEST-001 должен вернуться


async def test_sync_unknown_field_is_ignored(client, seeded):
    """
    Sync с несуществующим полем: applied == 0 (нет допустимых изменений).
    Нет ошибок — поле просто пропускается.
    """
    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [{"site_id": "BS-TEST-001", "nonexistent_field_xyz": "value"}],
        "client_version": 1,
    }, headers=manager_h)

    assert resp.status_code == 200
    data = resp.json()
    # clean_data пустой → строка пропускается → applied == 0
    assert data["applied"] == 0


async def test_sync_rejects_new_site_rows(client, seeded):
    """Sync не создаёт новый объект по неизвестному ID объекта."""
    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at": None,
        "project_id": seeded["ucn_project_id"],
        "rows": [{
            "site_id": "BS-NEW-001",
            "macroregion": "Дальний Восток",
        }],
        "client_version": 1,
    }, headers=manager_h)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["applied"] == 0
    assert len(data["errors"]) == 1
    assert "создание новых объектов через excel запрещено" in data["errors"][0].lower()

    list_resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=manager_h,
    )
    assert list_resp.status_code == 200
    site_ids = [item["site_id"] for item in list_resp.json()["items"]]
    assert "BS-NEW-001" not in site_ids


async def test_excel_sync_token_can_sync_matching_project(client, seeded):
    """Scoped Excel token должен работать на /sync в рамках своего project_id."""
    headers = token_headers(
        seeded["manager_id"],
        "manager",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at": None,
        "project_id": seeded["ucn_project_id"],
        "rows": [{
            "site_id": "BS-TEST-001",
            "macroregion": "Центр",
        }],
        "client_version": 1,
    }, headers=headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["applied"] == 1
    assert data["errors"] == []


async def test_excel_sync_token_rejects_other_project(client, seeded):
    """Scoped Excel token не должен позволять sync в другой project_id."""
    headers = token_headers(
        seeded["manager_id"],
        "manager",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at": None,
        "project_id": seeded["placeholder_project_id"],
        "rows": [],
        "client_version": 1,
    }, headers=headers)

    assert resp.status_code == 403


async def test_contractor_excel_sync_token_cannot_sync(client, seeded):
    """Даже с Excel token contractor не должен получать доступ к /sync."""
    headers = token_headers(
        seeded["contractor_user_id"],
        "contractor",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at": None,
        "project_id": seeded["ucn_project_id"],
        "rows": [],
        "client_version": 1,
    }, headers=headers)

    assert resp.status_code == 403


async def test_excel_sync_token_cannot_update_sites_from_other_project(client, seeded):
    """Scoped Excel token не должен менять site_id из чужого проекта даже при корректном body.project_id."""
    admin_h = token_headers(seeded["admin_id"], "admin")

    create_project = await client.post("/api/v1/projects/", json={
        "name": "Дополнительный UCN",
        "code": "ucn-extra",
        "module_key": "ucn_sites_v1",
    }, headers=admin_h)
    assert create_project.status_code == 201, create_project.text
    other_project_id = create_project.json()["id"]

    create_site = await client.post("/api/v1/sites/", json={
        "site_id": "BS-OTHER-001",
        "name": "Объект другого проекта",
        "project_id": other_project_id,
        "region": "Тверская область",
    }, headers=admin_h)
    assert create_site.status_code == 201, create_site.text

    scoped_headers = token_headers(
        seeded["admin_id"],
        "admin",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.post("/api/v1/sync", json={
        "last_sync_at": None,
        "project_id": seeded["ucn_project_id"],
        "rows": [{
            "site_id": "BS-OTHER-001",
            "macroregion": "Сибирь",
        }],
        "client_version": 1,
    }, headers=scoped_headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["applied"] == 0
    assert len(data["errors"]) == 1
    assert "другому проекту" in data["errors"][0].lower()


# ── POST /sync — контроль доступа ─────────────────────────────────────────────

async def test_viewer_cannot_sync(client, seeded):
    """Viewer не может вызвать /sync → 403."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.post("/api/v1/sync", json={
        "rows": [], "client_version": 1,
    }, headers=headers)
    assert resp.status_code == 403


async def test_contractor_cannot_sync(client, seeded):
    """Contractor не может вызвать /sync → 403 (require_manager)."""
    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.post("/api/v1/sync", json={
        "rows": [], "client_version": 1,
    }, headers=headers)
    assert resp.status_code == 403


async def test_unauthenticated_sync_returns_403(client, seeded):
    """Запрос без токена → 403."""
    resp = await client.post("/api/v1/sync", json={"rows": []})
    assert resp.status_code == 403


# ── GET /sync/history ─────────────────────────────────────────────────────────

async def test_manager_can_view_history(client, seeded):
    """Manager может просматривать историю объекта."""
    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.get(
        f"/api/v1/sync/history/{seeded['site_pk']}",
        headers=manager_h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data


async def test_viewer_cannot_view_history(client, seeded):
    """Viewer не может просматривать историю → 403."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.get(
        f"/api/v1/sync/history/{seeded['site_pk']}",
        headers=headers,
    )
    assert resp.status_code == 403


async def test_admin_can_get_history_field_metadata(client, seeded):
    """Статический route /history-fields не должен перехватываться /history/{site_id}."""
    admin_h = token_headers(seeded["admin_id"], "admin")
    resp = await client.get("/api/v1/sync/history-fields", headers=admin_h)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert any(item["field_name"] == "macroregion" for item in data)


# ── POST /sync/rollback-entry ─────────────────────────────────────────────────

async def test_rollback_entry_restores_field_value(client, seeded):
    """
    Сценарий rollback-entry:
    1. Sync обновляет macroregion: None → "До отката"
    2. GET /history → находим запись с old_value=None
    3. POST /rollback-entry → rolled_back_fields содержит macroregion
    """
    manager_h = token_headers(seeded["manager_id"], "manager")
    admin_h   = token_headers(seeded["admin_id"],   "admin")

    # Шаг 1: Sync задаёт значение
    sync_resp = await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [{"site_id": "BS-TEST-001", "macroregion": "До отката"}],
        "client_version": 1,
    }, headers=manager_h)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["applied"] == 1

    # Шаг 2: Получить историю
    hist_resp = await client.get(
        f"/api/v1/sync/history/{seeded['site_pk']}",
        headers=manager_h,
    )
    assert hist_resp.status_code == 200
    items = hist_resp.json()["items"]
    tip_entry = next(
        (e for e in items if e["field_name"] == "macroregion"),
        None,
    )
    assert tip_entry is not None, f"Нет записи macroregion в истории: {items}"
    assert tip_entry["new_value"] == "До отката"

    # Шаг 3: Rollback
    rb_resp = await client.post("/api/v1/sync/rollback-entry", json={
        "history_id": tip_entry["id"],
    }, headers=admin_h)
    assert rb_resp.status_code == 200
    rb_data = rb_resp.json()
    assert rb_data["success"] is True
    assert "macroregion" in rb_data["rolled_back_fields"]


async def test_rollback_entry_manager_forbidden(client, seeded):
    """Manager не может выполнить rollback-entry → 403 (только admin)."""
    manager_h = token_headers(seeded["manager_id"], "manager")

    # Создаём историческую запись через sync
    await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [{"site_id": "BS-TEST-001", "smr_order_status": "в работе"}],
        "client_version": 1,
    }, headers=manager_h)

    hist_resp = await client.get(
        f"/api/v1/sync/history/{seeded['site_pk']}",
        headers=manager_h,
    )
    items = hist_resp.json()["items"]
    assert len(items) > 0, "Должны быть записи истории"

    rb_resp = await client.post("/api/v1/sync/rollback-entry", json={
        "history_id": items[0]["id"],
    }, headers=manager_h)  # manager, не admin!
    assert rb_resp.status_code == 403


async def test_rollback_nonexistent_entry_returns_404(client, seeded):
    """Rollback несуществующей записи → 404."""
    admin_h = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/sync/rollback-entry", json={
        "history_id": 999999,
    }, headers=admin_h)
    assert resp.status_code == 404


# ── POST /sync/rollback (timestamp-based) ─────────────────────────────────────

async def test_rollback_by_timestamp(client, seeded):
    """
    POST /rollback с to_timestamp, предшествующим изменению.

    Логика get_field_value_at:
      Ищет историю с changed_at >= to_timestamp.
      Если нашёл — возвращает old_value (значение ДО изменения).

    Используем фиксированную дату в прошлом (2024-01-01), гарантированно
    меньше любого changed_at, создаваемого в тестовой сессии 2026 года.
    """
    from datetime import datetime, timezone

    manager_h = token_headers(seeded["manager_id"], "manager")
    admin_h   = token_headers(seeded["admin_id"],   "admin")

    # Фиксированная точка в прошлом (до любого изменения в тестовой БД)
    rollback_to = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Синхронизируем изменение (changed_at = now() > rollback_to)
    sync_r = await client.post("/api/v1/sync", json={
        "last_sync_at":  None,
        "project_id":    seeded["ucn_project_id"],
        "rows": [{"site_id": "BS-TEST-001", "macroregion": "Значение для отката"}],
        "client_version": 1,
    }, headers=manager_h)
    assert sync_r.json()["applied"] == 1

    # Откатываем к rollback_to:
    #   get_field_value_at найдёт запись (changed_at >= 2024-01-01) и вернёт
    #   old_value = None (значение до первой синхронизации)
    rb_resp = await client.post("/api/v1/sync/rollback", json={
        "site_id":      "BS-TEST-001",
        "field_name":   "macroregion",
        "to_timestamp": rollback_to.isoformat(),
    }, headers=admin_h)
    assert rb_resp.status_code == 200
    data = rb_resp.json()
    assert data["success"] is True
    # macroregion было "Значение для отката", rollback ставит old_value=None → изменение
    assert "macroregion" in data["rolled_back_fields"]


async def test_rollback_requires_admin(client, seeded):
    """POST /rollback для viewer → 403."""
    viewer_h = token_headers(seeded["viewer_id"], "viewer")
    resp = await client.post("/api/v1/sync/rollback", json={
        "site_id":      "BS-TEST-001",
        "to_timestamp": "2024-01-01T00:00:00Z",
    }, headers=viewer_h)
    assert resp.status_code == 403


async def test_rollback_nonexistent_site_returns_404(client, seeded):
    """POST /rollback для несуществующего объекта → 404."""
    admin_h = token_headers(seeded["admin_id"], "admin")
    resp = await client.post("/api/v1/sync/rollback", json={
        "site_id":      "BS-NONEXISTENT-9999",
        "to_timestamp": "2024-01-01T00:00:00Z",
    }, headers=admin_h)
    assert resp.status_code == 404


# ── GET /sync/columns ─────────────────────────────────────────────────────────

async def test_columns_endpoint_returns_list(client, seeded):
    """GET /sync/columns возвращает список колонок для VBA."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get("/api/v1/sync/columns", headers=headers)
    assert resp.status_code == 200
    columns = resp.json()
    assert isinstance(columns, list)
    assert len(columns) > 0
    # Ключевой столбец site_id должен присутствовать
    db_names = [c["db_name"] for c in columns]
    assert "site_id" in db_names


async def test_columns_accept_excel_sync_token(client, seeded):
    """GET /sync/columns должен принимать scoped Excel token."""
    headers = token_headers(
        seeded["manager_id"],
        "manager",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.get("/api/v1/sync/columns", headers=headers)
    assert resp.status_code == 200
    db_names = [c["db_name"] for c in resp.json()]
    assert "site_id" in db_names


async def test_columns_require_auth(client, seeded):
    """GET /sync/columns без токена → 403."""
    resp = await client.get("/api/v1/sync/columns")
    assert resp.status_code == 403
