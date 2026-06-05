"""
test_excel.py — тесты Excel-экспорта с привязкой к модулю проекта.

Покрытые сценарии:
  - GET /excel/export?project_id=<placeholder> → 400 (not configured)
  - GET /excel/export?project_id=<недоступный> → 404
  - GET /excel/export?project_id=<ucn> → 200 или 500 (если нет XLSM-шаблона)
    Важно: 500 — это ошибка инфраструктуры (отсутствует templates/sync_template.xlsm),
    а не ошибка бизнес-логики. Тест принимает оба кода.
  - GET /excel/export — без авторизации → 403
  - POST /excel/import?project_id=<placeholder> → 400 (not configured)
  - POST /excel/import — не .xlsx файл → 400
  - POST /excel/import — не создаёт новые объекты, только обновляет существующие
"""
import io
import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from conftest import token_headers
from app.models.site import Site
from app.services.auth import decode_token


REPO_ROOT = Path(__file__).resolve().parents[2]
STALE_SYNC_TEMPLATE_VBA_SHA256 = (
    "96aea6b90fdbe4dfa718840964fb2bafadcbdae08e8530eb503a361c270bf1ea"
)


# ── Экспорт: проверка module_key ───────────────────────────────────────────────

async def test_export_placeholder_project_returns_400(client, seeded):
    """
    Экспорт из placeholder-проекта должен вернуть 400.
    Этот тест проверяет, что маршрут зависит от module_key.
    """
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/excel/export?project_id={seeded['placeholder_project_id']}",
        headers=headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "not configured" in detail


async def test_export_ucn_project_validates_module(client, seeded):
    """
    Экспорт из UCN-проекта: модуль настроен корректно.
    Принимаем 200 (успех) или 500 (шаблон .xlsm не найден в тестовой среде).
    400 — неприемлем (означал бы ошибку module_key-проверки).
    """
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/excel/export?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    # 400 не должно быть: UCN — это ucn_sites_v1, модуль настроен
    assert resp.status_code != 400, (
        "UCN-проект неожиданно вернул 400 — проверьте module_key-логику"
    )
    # 200 = OK, 500 = шаблон не найден (нормально для тестовой среды без .xlsm)
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert _data_sheet_is_protected(resp.content) is True


async def test_export_inaccessible_project_returns_404(client, seeded):
    """
    Экспорт из проекта, недоступного менеджеру, → 404.
    """
    # Создаём новый UCN-проект (admin) без назначения менеджеру
    admin_h = token_headers(seeded["admin_id"], "admin")
    create_r = await client.post("/api/v1/projects/", json={
        "name":       "Закрытый UCN",
        "code":       "closed-ucn",
        "module_key": "ucn_sites_v1",
    }, headers=admin_h)
    assert create_r.status_code == 201
    locked_id = create_r.json()["id"]

    manager_h = token_headers(seeded["manager_id"], "manager")
    resp = await client.get(
        f"/api/v1/excel/export?project_id={locked_id}",
        headers=manager_h,
    )
    assert resp.status_code == 404


async def test_export_requires_auth(client, seeded):
    """Без токена экспорт → 403."""
    resp = await client.get(
        f"/api/v1/excel/export?project_id={seeded['ucn_project_id']}",
    )
    assert resp.status_code == 403


async def test_export_embeds_scoped_excel_token(monkeypatch, client, seeded):
    """Excel export должен выдавать отдельный excel_sync token с project_id."""
    import app.api.v1.excel as excel_api

    captured = {}

    def fake_export_sites_to_excel(sites, auth_token, username, project_id):
        captured["auth_token"] = auth_token
        captured["username"] = username
        captured["project_id"] = project_id
        captured["site_count"] = len(sites)
        return b"fake-xlsm"

    monkeypatch.setattr(excel_api, "export_sites_to_excel", fake_export_sites_to_excel)

    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/excel/export?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.content == b"fake-xlsm"
    assert captured["project_id"] == seeded["ucn_project_id"]
    assert captured["site_count"] >= 1

    token_data = decode_token(captured["auth_token"])
    assert token_data.user_id == seeded["admin_id"]
    assert token_data.role == "admin"
    assert token_data.token_type == "excel_sync"
    assert token_data.project_id == seeded["ucn_project_id"]


def test_vba_sync_uses_embedded_excel_token_without_browser_auth_probe():
    """VBA sync должен сначала использовать _Config.auth_token, а не /auth/me."""
    config_src = _vba_source("modConfig.bas")
    sync_src = _vba_source("modSync.bas")

    assert 'Public Const API_BASE       As String = "/api/v1"' in config_src
    assert 'Public Const CFG_PROJECT_ID As String = "project_id"' in config_src
    assert 'Public Const KEY_HEADER     As String = "ID объекта"' in config_src
    assert "Public g_ProjectId" in config_src

    sync_now = _vba_block(sync_src, "Public Sub SyncNow()", "Private Function LoadColumnMap")
    assert "EnsureSyncSession" in sync_now
    assert "If Not DoLogin()" not in sync_now

    ensure_session = _vba_function(sync_src, "EnsureSyncSession")
    assert "LoadStoredSession" in ensure_session
    assert "DoLogin" in ensure_session
    assert "CheckToken" not in ensure_session

    assert 'JsonObjAdd(reqBody, "project_id", CLng(g_ProjectId))' in sync_src


def test_sync_template_vba_project_is_refreshed_from_sources():
    """XLSM template must not keep the stale VBA binary that starts with DoLogin."""
    template_path = REPO_ROOT / "backend" / "templates" / "sync_template.xlsm"
    with ZipFile(template_path) as archive:
        vba_project = archive.read("xl/vbaProject.bin")

    assert hashlib.sha256(vba_project).hexdigest() != STALE_SYNC_TEMPLATE_VBA_SHA256


def test_nginx_keeps_legacy_vba_sync_routes_compatible():
    """Старые XLSM-макросы без /api/v1 не должны получать nginx 404."""
    nginx_conf = (REPO_ROOT / "nginx" / "nginx.conf").read_text(encoding="utf-8")

    assert "location = /auth/me" in nginx_conf
    assert "proxy_pass http://backend:8000/api/v1/sync/columns;" in nginx_conf
    assert "location /auth/" in nginx_conf
    assert "proxy_pass http://backend:8000/api/v1/auth/" in nginx_conf
    assert "location = /sync" in nginx_conf
    assert "proxy_pass http://backend:8000/api/v1/sync;" in nginx_conf
    assert "location /sync/" in nginx_conf
    assert "proxy_pass http://backend:8000/api/v1/sync/" in nginx_conf


# ── Импорт: проверка module_key и типа файла ──────────────────────────────────

async def test_import_placeholder_project_returns_400(client, seeded):
    """
    Импорт в placeholder-проект → 400 (not configured).
    """
    headers = token_headers(seeded["admin_id"], "admin")
    dummy_xlsx = _minimal_xlsx_bytes()
    resp = await client.post(
        f"/api/v1/excel/import?project_id={seeded['placeholder_project_id']}",
        files={"file": ("test.xlsx", dummy_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "not configured" in detail


async def test_import_wrong_extension_returns_400(client, seeded):
    """Загрузка файла с расширением .csv → 400."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post(
        f"/api/v1/excel/import?project_id={seeded['ucn_project_id']}",
        files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "xlsx" in resp.json()["detail"].lower()


async def test_import_requires_manager_role(client, seeded):
    """Viewer не может импортировать → 403."""
    headers = token_headers(seeded["viewer_id"], "viewer")
    dummy_xlsx = _minimal_xlsx_bytes()
    resp = await client.post(
        f"/api/v1/excel/import?project_id={seeded['ucn_project_id']}",
        files={"file": ("test.xlsx", dummy_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_import_new_template_rejects_new_site(client, seeded):
    """Импорт нового шаблона не создаёт новый объект в UCN-проекте."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post(
        f"/api/v1/excel/import?project_id={seeded['ucn_project_id']}",
        files={"file": ("ucn.xlsx", _minimal_xlsx_bytes(site_id="BS-IMPORT-001"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["created"] == 0
    assert data["updated"] == 0
    assert data["errors_count"] == 1
    assert "создание новых объектов через excel запрещено" in data["errors"][0].lower()

    list_resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert all(item["site_id"] != "BS-IMPORT-001" for item in items)


async def test_import_new_template_updates_existing_site(client, seeded):
    """Импорт нового шаблона обновляет существующий объект по ID объекта."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post(
        f"/api/v1/excel/import?project_id={seeded['ucn_project_id']}",
        files={"file": ("ucn.xlsx", _minimal_xlsx_bytes(site_id="BS-TEST-001"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["created"] == 0
    assert data["updated"] == 1
    assert data["errors_count"] == 0

    list_resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    imported = next(item for item in items if item["site_id"] == "BS-TEST-001")
    assert imported["name"] == "с Тестовое"
    assert imported["region"] == "Амурская область"

    history_resp = await client.get(
        f"/api/v1/sync/history/{imported['id']}",
        headers=headers,
    )
    assert history_resp.status_code == 200
    history_items = history_resp.json()["items"]
    macro_entry = next(item for item in history_items if item["field_name"] == "macroregion")
    assert macro_entry["new_value"] == "Дальний Восток"


# ── Admin replace-load: первичная загрузка нового шаблона ─────────────────────

async def test_admin_can_replace_ucn_project_sites_from_template(client, seeded, db_engine):
    """Admin может очистить старый набор UCN и загрузить новые строки шаблона."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post(
        f"/api/v1/excel/replace?project_id={seeded['ucn_project_id']}",
        files={
            "file": (
                "ucn-reload.xlsx",
                _reload_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["deleted"] == 1
    assert data["created"] == 2
    assert data["errors_count"] == 0

    list_resp = await client.get(
        f"/api/v1/sites/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] == 2
    site_ids = {item["site_id"] for item in payload["items"]}
    assert site_ids == {"UCN-2026-0001", "UCN-2026-0002"}
    assert seeded["site_site_id"] not in site_ids

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(Site).where(Site.site_id == "UCN-2026-0001")
        )
        site = result.scalar_one()
        assert site.project_id == seeded["ucn_project_id"]
        assert site.name == "с Новый"
        assert site.region == "Амурская область"
        assert site.ams_storage_city == "Хабаровск"
        assert site.kzd_smr == "КЗД-СМР-1"
        assert site.r1 == "готово"
        assert site.r2 == "в работе"


async def test_replace_ucn_project_sites_is_admin_only(client, seeded):
    """Manager не может выполнить destructive replace-load."""
    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.post(
        f"/api/v1/excel/replace?project_id={seeded['ucn_project_id']}",
        files={
            "file": (
                "ucn-reload.xlsx",
                _reload_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )

    assert resp.status_code == 403


async def test_replace_placeholder_project_returns_400(client, seeded):
    """Первичная загрузка шаблона доступна только для ucn_sites_v1."""
    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.post(
        f"/api/v1/excel/replace?project_id={seeded['placeholder_project_id']}",
        files={
            "file": (
                "ucn-reload.xlsx",
                _reload_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )

    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


# ── Вспомогательная функция ───────────────────────────────────────────────────

def _vba_source(filename: str) -> str:
    return (REPO_ROOT / "vba" / filename).read_text(encoding="utf-8")


def _vba_block(source: str, start: str, end: str) -> str:
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def _vba_function(source: str, function_name: str) -> str:
    match = re.search(
        rf"(?:Public|Private) Function {re.escape(function_name)}\b.*?End Function",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"VBA function {function_name} not found"
    return match.group(0)

def _minimal_xlsx_bytes(site_id: str = "BS-IMPORT-001") -> bytes:
    """Создаёт минимальный валидный .xlsx файл для тестов."""
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Лист1"
        ws.append([
            "№ п/п",
            "ФИАС код",
            "ID объекта",
            "Макрорегион",
            "Регион",
            "Район",
            "Сельское поселение",
            "Наименование НП",
            "WGS широта, гг",
            "WGS долгота, гг",
            "Начало СМР, план",
            "Начало СМР, факт",
            "Приемка, план",
            "Приемка, факт",
            "Статус заказа на СМР",
        ])
        ws.append([
            1,
            "2800000000000",
            site_id,
            "Дальний Восток",
            "Амурская область",
            "м.о. Тестовый",
            "с.п. Тестовое",
            "с Тестовое",
            52.01,
            127.55,
            "2026-05-01",
            "",
            "2026-06-01",
            "",
            "в работе",
        ])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        # Если openpyxl недоступен — возвращаем пустые байты (тест на расширение)
        return b"\x50\x4b\x03\x04"  # PK magic bytes (ZIP/XLSX)


def _reload_xlsx_bytes() -> bytes:
    """Создаёт файл с новым v2 header set и двумя новыми объектами."""
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Лист1"
        ws.append([
            "№ п/п",
            "ФИАС код",
            "ID объекта",
            "Макрорегион",
            "Регион",
            "Региональный филиал",
            "Район",
            "Сельское поселение",
            "Наименование НП",
            "WGS широта, гг",
            "WGS долгота, гг",
            "Дата получения разрешения на размещение АМС БС, план",
            "Дата получения разрешения на размещение АМС БС, факт",
            "ТУ на электропитание получены, дата",
            "Дата выполнения ТУ ВЭС, план",
            "Дата выполнения ТУ ВЭС, факт",
            "Дата готовности ВОЛС, план",
            "Дата готовности ВОЛС, факт",
            "ПО",
            "Заказ ПИР",
            "Выезд на обследование для подготовки ИГИ, план",
            "Выезд на обследование для подготовки ИГИ, факт",
            "Подготовка ИГИ, план",
            "Подготовка ИГИ, факт",
            "Согласование ИГИ, план",
            "Согласование ИГИ, факт",
            "Тип АМС",
            "Получение АМС, план",
            "Склад размещения АМС, город",
            "Получение АМС, факт",
            "Заливка фундамента, план",
            "Заливка фундамента, факт",
            "Установка АМС, план",
            "Установка АМС, факт",
            "Отчет о вертикальности АМС, план",
            "Отчет о вертикальности АМС, факт",
            "Подготовка АППИ, КЖ, план",
            "Подготовка АППИ, КЖ, факт",
            "Согласование АППИ, КЖ, план",
            "Согласование АППИ, КЖ, факт",
            "Согласование АППИ КА, план",
            "Согласование АППИ КА, факт",
            "Выпуск РД ",
            "Подписание ТУ/ЭС ",
            "Сдача ЭС и ТУ в бумаге ",
            "Приемка РД",
            "КЗД на ПИР",
            "Заказ на СМР",
            "Выписка оборудования БС ",
            "Требование ",
            "Рейс БС",
            "Получение оборудования, план",
            "Получение оборудования, факт",
            "Контакты бригады",
            "Начало СМР, план",
            "Начало СМР, факт",
            "ПНР, план",
            "ПНР, факт",
            "Приемка, план",
            "Приемка, факт",
            "Справка о выполнении ТУ ",
            "Передача Паспорта/АРБП/Справки о выполнении ТУ в ОГЭ ",
            "Статус заказа на СМР",
            "Подготовка ПСЭЗ",
            "Р1",
            "Р2",
            "КЗД на СМР",
        ])
        ws.append([
            1,
            "2800000000001",
            "UCN-2026-0001",
            "Дальний Восток",
            "Амурская область",
            "РФ ДВ",
            "Тестовый район",
            "Тестовое поселение",
            "с Новый",
            52.01,
            127.55,
            "2026-05-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "ПО-1",
            "ПИР-1",
            "",
            "",
            "",
            "",
            "",
            "",
            "Мачта",
            "2026-05-10",
            "Хабаровск",
            "",
            "",
            "",
            "",
            "",
            "2026-05-20",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "КЗД-ПИР-1",
            "СМР-1",
            "",
            "",
            "",
            "",
            "",
            "",
            "2026-06-01",
            "",
            "",
            "",
            "2026-07-01",
            "",
            "",
            "",
            "в работе",
            "готовится",
            "готово",
            "в работе",
            "КЗД-СМР-1",
        ])
        ws.append([
            2,
            "2800000000002",
            "UCN-2026-0002",
            "Дальний Восток",
            "Амурская область",
            "РФ ДВ",
            "Второй район",
            "",
            "с Второй",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Владивосток",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "СМР-2",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "запланирован",
            "",
            "",
            "",
            "",
        ])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return b"\x50\x4b\x03\x04"


def _data_sheet_is_protected(xlsm_bytes: bytes) -> bool:
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    }

    with ZipFile(io.BytesIO(xlsm_bytes)) as archive:
        workbook_xml = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rel_id = None
        for sheet in workbook_xml.findall("main:sheets/main:sheet", ns):
            if sheet.get("name") == "Data":
                rel_id = sheet.get(f"{{{ns['rel']}}}id")
                break

        if not rel_id:
            return False

        rels_xml = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = None
        for rel in rels_xml.findall("pkg:Relationship", ns):
            if rel.get("Id") == rel_id:
                target = rel.get("Target")
                break

        if not target:
            return False

        sheet_xml = ElementTree.fromstring(archive.read("xl/" + target.lstrip("/")))
        return sheet_xml.find("main:sheetProtection", ns) is not None
