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
from xml.etree import ElementTree
from zipfile import ZipFile
import pytest
from conftest import token_headers
from app.services.auth import decode_token


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


# ── Вспомогательная функция ───────────────────────────────────────────────────

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
