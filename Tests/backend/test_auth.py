"""
test_auth.py — тесты аутентификации.

Покрытые сценарии:
  - Успешный логин возвращает access_token
  - Неверный пароль → 401
  - Несуществующий пользователь → 401
  - GET /auth/me возвращает текущего пользователя
  - GET /auth/me без токена → 403
  - GET /auth/me с просроченным/невалидным токеном → 401
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from conftest import token_headers
from app.models.log import ActionLog


async def test_login_success(client, seeded):
    """Успешный логин возвращает JWT-токен и тип 'bearer'."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "t_admin",
        "password": "Admin1234",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_persists_action_log_without_dependency_autocommit(client_no_autocommit, seeded, db_engine):
    """Login should still persist its audit log without dependency auto-commit."""
    resp = await client_no_autocommit.post("/api/v1/auth/login", json={
        "username": "t_admin",
        "password": "Admin1234",
    })
    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(ActionLog)
            .where(ActionLog.action == "login", ActionLog.user_id == seeded["admin_id"])
            .order_by(ActionLog.id.desc())
        )
        log = result.scalars().first()

    assert log is not None


async def test_login_wrong_password(client, seeded):
    """Неверный пароль → 401."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "t_admin",
        "password": "WrongPass999",
    })
    assert resp.status_code == 401


async def test_login_unknown_user(client, seeded):
    """Несуществующий пользователь → 401."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "nobody_here",
        "password": "anything",
    })
    assert resp.status_code == 401


async def test_me_returns_current_user(client, seeded):
    """GET /auth/me возвращает username и role текущего пользователя."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "t_admin"
    assert data["role"] == "admin"


async def test_me_requires_auth(client, seeded):
    """GET /auth/me без Authorization-заголовка → 403 (HTTPBearer auto_error)."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403


async def test_me_with_invalid_token(client, seeded):
    """GET /auth/me с испорченным токеном → 401."""
    headers = {"Authorization": "Bearer totally.invalid.token"}
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_me_rejects_excel_sync_token(client, seeded):
    """Обычный auth-endpoint не должен принимать scoped Excel token."""
    headers = token_headers(
        seeded["admin_id"],
        "admin",
        token_type="excel_sync",
        project_id=seeded["ucn_project_id"],
    )
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401


async def test_me_for_each_role(client, seeded):
    """Каждая роль может получить данные о себе."""
    role_user_map = [
        (seeded["admin_id"],           "admin"),
        (seeded["manager_id"],         "manager"),
        (seeded["viewer_id"],          "viewer"),
        (seeded["contractor_user_id"], "contractor"),
    ]
    for user_id, role in role_user_map:
        headers = token_headers(user_id, role)
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200, f"role={role} failed: {resp.text}"
        assert resp.json()["role"] == role


async def test_user_can_update_own_username_and_login_with_new_username(client, seeded):
    """Пользователь может изменить свой логин через PATCH /auth/me."""
    headers = token_headers(seeded["manager_id"], "manager")

    resp = await client.patch("/api/v1/auth/me", json={"username": "t_manager_new"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "t_manager_new"

    old_login = await client.post("/api/v1/auth/login", json={
        "username": "t_manager",
        "password": "Mgr1234",
    })
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={
        "username": "t_manager_new",
        "password": "Mgr1234",
    })
    assert new_login.status_code == 200, new_login.text


async def test_user_can_update_own_password_and_log_is_sanitized(client, seeded, db_engine):
    """Self-update меняет пароль и не пишет его в action_logs.extra."""
    headers = token_headers(seeded["viewer_id"], "viewer")

    resp = await client.patch("/api/v1/auth/me", json={"password": "View56789"}, headers=headers)
    assert resp.status_code == 200, resp.text

    old_login = await client.post("/api/v1/auth/login", json={
        "username": "t_viewer",
        "password": "View1234",
    })
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={
        "username": "t_viewer",
        "password": "View56789",
    })
    assert new_login.status_code == 200, new_login.text

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(ActionLog)
            .where(ActionLog.action == "user_update")
            .order_by(ActionLog.id.desc())
        )
        log = result.scalars().first()

    assert log is not None
    assert "password" not in (log.extra or {})
    assert log.extra["password_changed"] is True


async def test_self_update_rejects_existing_username(client, seeded):
    """Self-update не даёт занять уже существующий username."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.patch("/api/v1/auth/me", json={"username": "t_admin"}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Username already exists"


async def test_admin_can_update_other_user_username_and_password(client, seeded):
    """Admin может сменить логин и пароль другому пользователю."""
    headers = token_headers(seeded["admin_id"], "admin")

    resp = await client.patch(
        f"/api/v1/users/{seeded['viewer_id']}",
        json={"username": "t_viewer_new", "password": "View99999"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "t_viewer_new"

    old_login = await client.post("/api/v1/auth/login", json={
        "username": "t_viewer",
        "password": "View1234",
    })
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={
        "username": "t_viewer_new",
        "password": "View99999",
    })
    assert new_login.status_code == 200, new_login.text
