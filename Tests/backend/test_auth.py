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
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from conftest import token_headers
from app.models.log import ActionLog
from app.models.user import User, UserRole
from app.services.ldap_auth import LdapAuthenticatedUser


def test_ldap_group_mapping_accepts_ad_member_dns():
    """AD memberOf DN с CN=tracker_users маппится в manager."""
    from app.services.ldap_auth import _role_from_groups

    role = _role_from_groups([
        "CN=tracker_users,OU=Groups,DC=example,DC=local",
    ])

    assert role == UserRole.manager


def test_ldap_group_mapping_admin_has_priority():
    """tracker_admins приоритетнее tracker_users."""
    from app.services.ldap_auth import _role_from_groups

    role = _role_from_groups([
        "CN=tracker_users,OU=Groups,DC=example,DC=local",
        "CN=tracker_admins,OU=Groups,DC=example,DC=local",
    ])

    assert role == UserRole.admin


def test_ldap_result_summary_keeps_diagnostics():
    """LDAP result summary keeps useful server diagnostics."""
    from app.services.ldap_auth import _ldap_result_summary

    class FakeConnection:
        result = {
            "result": 49,
            "description": "invalidCredentials",
            "message": "80090308: data 52e",
        }

    summary = _ldap_result_summary(FakeConnection())

    assert "result=49" in summary
    assert "description=invalidCredentials" in summary
    assert "message=80090308: data 52e" in summary


def test_ldap_log_event_does_not_log_password(caplog):
    """LDAP diagnostics must not leak passwords."""
    from app.services.ldap_auth import _log_ldap_event

    caplog.set_level(logging.INFO, logger="app.services.ldap_auth")

    _log_ldap_event(
        logging.INFO,
        "test event",
        username="ad_user",
        bind_password="SuperSecret123",
        password="SuperSecret123",
        server_url="ldaps://rtk-service.ru:636",
    )

    assert "test event" in caplog.text
    assert "ad_user" in caplog.text
    assert "ldaps://rtk-service.ru:636" in caplog.text
    assert "SuperSecret123" not in caplog.text
    assert "bind_password" not in caplog.text


def test_ldap_server_urls_support_single_and_comma_list(monkeypatch):
    """LDAP server URLs can be configured as one URL or a comma-separated list."""
    from app.config import settings
    from app.services.ldap_auth import _ldap_server_urls

    old_url = settings.LDAP_SERVER_URL
    old_urls = settings.LDAP_SERVER_URLS
    try:
        settings.LDAP_SERVER_URL = "ldaps://dc1.rtk-service.ru:636"
        settings.LDAP_SERVER_URLS = None
        assert _ldap_server_urls() == ["ldaps://dc1.rtk-service.ru:636"]

        settings.LDAP_SERVER_URLS = (
            "ldaps://dc1.rtk-service.ru:636, ldap://dc2.rtk-service.ru:389"
        )
        assert _ldap_server_urls() == [
            "ldaps://dc1.rtk-service.ru:636",
            "ldap://dc2.rtk-service.ru:389",
        ]
    finally:
        settings.LDAP_SERVER_URL = old_url
        settings.LDAP_SERVER_URLS = old_urls


def test_ldap_server_options_disable_referrals_and_schema_lookup_by_default():
    """Defaults should avoid extra network hops in locked-down intranets."""
    from app.services.ldap_auth import _ldap_auto_referrals, _ldap_get_info

    assert _ldap_auto_referrals() is False
    assert _ldap_get_info() == "NONE"


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


async def test_ldap_login_creates_manager_for_tracker_users(
    client,
    seeded,
    db_engine,
    monkeypatch,
):
    """LDAP user из tracker_users создаётся локально как manager."""
    from app.api.v1 import auth as auth_api
    from app.config import settings

    old_backend = settings.AUTH_BACKEND
    settings.AUTH_BACKEND = "ldap"

    async def fake_ldap_authenticate(username, password):
        assert username == "ad_user"
        assert password == "AdPass123"
        return LdapAuthenticatedUser(
            username="ad_user",
            full_name="AD User",
            email="ad_user@example.local",
            role=UserRole.manager,
            groups=["tracker_users"],
        )

    monkeypatch.setattr(auth_api, "authenticate_ldap_user", fake_ldap_authenticate)
    try:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "ad_user",
            "password": "AdPass123",
        })
    finally:
        settings.AUTH_BACKEND = old_backend

    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "ad_user"))
        ).scalar_one()

    assert user.email == "ad_user@example.local"
    assert user.full_name == "AD User"
    assert user.role == UserRole.manager
    assert user.is_active is True


async def test_ldap_login_admin_group_has_priority(
    client,
    seeded,
    db_engine,
    monkeypatch,
):
    """Если LDAP вернул обе группы, tracker_admins побеждает tracker_users."""
    from app.api.v1 import auth as auth_api
    from app.config import settings

    old_backend = settings.AUTH_BACKEND
    settings.AUTH_BACKEND = "ldap"

    async def fake_ldap_authenticate(username, password):
        return LdapAuthenticatedUser(
            username=username,
            full_name="AD Admin",
            email="ad_admin@example.local",
            role=UserRole.admin,
            groups=["tracker_users", "tracker_admins"],
        )

    monkeypatch.setattr(auth_api, "authenticate_ldap_user", fake_ldap_authenticate)
    try:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "ad_admin",
            "password": "AdPass123",
        })
    finally:
        settings.AUTH_BACKEND = old_backend

    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "ad_admin"))
        ).scalar_one()

    assert user.role == UserRole.admin


async def test_ldap_login_updates_existing_user_role(
    client,
    seeded,
    db_engine,
    monkeypatch,
):
    """Повторный LDAP login синхронизирует роль существующего локального user."""
    from app.api.v1 import auth as auth_api
    from app.config import settings

    old_backend = settings.AUTH_BACKEND
    settings.AUTH_BACKEND = "ldap"

    async def fake_ldap_authenticate(username, password):
        return LdapAuthenticatedUser(
            username="t_manager",
            full_name="Promoted Manager",
            email="manager@test.local",
            role=UserRole.admin,
            groups=["tracker_admins"],
        )

    monkeypatch.setattr(auth_api, "authenticate_ldap_user", fake_ldap_authenticate)
    try:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "t_manager",
            "password": "AdPass123",
        })
    finally:
        settings.AUTH_BACKEND = old_backend

    assert resp.status_code == 200, resp.text

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "t_manager"))
        ).scalar_one()

    assert user.role == UserRole.admin
    assert user.full_name == "Promoted Manager"


async def test_ldap_login_failure_returns_401(client, seeded, monkeypatch):
    """Неуспешная LDAP-аутентификация → 401."""
    from app.api.v1 import auth as auth_api
    from app.config import settings

    old_backend = settings.AUTH_BACKEND
    settings.AUTH_BACKEND = "ldap"

    async def fake_ldap_authenticate(username, password):
        return None

    monkeypatch.setattr(auth_api, "authenticate_ldap_user", fake_ldap_authenticate)
    try:
        resp = await client.post("/api/v1/auth/login", json={
            "username": "ad_user",
            "password": "WrongPass999",
        })
    finally:
        settings.AUTH_BACKEND = old_backend

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
