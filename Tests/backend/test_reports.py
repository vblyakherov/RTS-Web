"""
test_reports.py — тесты для проектного раздела отчетов.

Покрытые сценарии:
  - GET /reports/?project_id=<ucn> → список доступных UCN-отчетов
  - GET /reports/?project_id=<placeholder> → пустой список
  - GET /reports/{key}?project_id=<ucn> → структурированный payload отчета
  - contractor видит агрегаты только по своим объектам
  - для placeholder detail-отчет недоступен
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.contractor import Contractor
from app.models.site import Site, SiteStatus

from conftest import token_headers


async def test_ucn_project_returns_available_reports(client, seeded):
    headers = token_headers(seeded["admin_id"], "admin")

    resp = await client.get(
        f"/api/v1/reports/?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    keys = {item["key"] for item in resp.json()}
    assert keys == {"status_overview", "milestone_readiness"}


async def test_placeholder_project_returns_empty_reports_list(client, seeded):
    headers = token_headers(seeded["admin_id"], "admin")

    resp = await client.get(
        f"/api/v1/reports/?project_id={seeded['placeholder_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json() == []


async def test_status_overview_report_returns_aggregated_payload(client, seeded, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with factory() as session:
        base_site = await session.get(Site, seeded["site_pk"])
        base_site.status = SiteStatus.construction
        base_site.region = "Москва"
        base_site.planned_end = now - timedelta(days=5)

        session.add(
            Site(
                site_id="BS-TEST-002",
                name="Тестовый объект 002",
                project_id=seeded["ucn_project_id"],
                region="Тверь",
                status=SiteStatus.accepted,
                planned_end=now - timedelta(days=1),
                actual_end=now - timedelta(hours=12),
            )
        )
        await session.commit()

    headers = token_headers(seeded["admin_id"], "admin")
    resp = await client.get(
        f"/api/v1/reports/status_overview?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "status_overview"
    assert data["title"]

    summary = {item["label"]: item["value"] for item in data["summary"]}
    assert summary["Всего объектов"] == "2"
    assert summary["Просрочено"] == "1"
    assert summary["Принято"] == "1"

    assert len(data["charts"]) == 2
    assert any(row["label"] == "Строительство" for row in data["charts"][0]["rows"])
    assert any(sheet["name"] == "Regions" for sheet in data["export_sheets"])


async def test_contractor_reports_are_scoped_to_own_sites(client, seeded, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with factory() as session:
        other_contractor = Contractor(name="ООО Другой подрядчик")
        session.add(other_contractor)
        await session.flush()

        session.add(
            Site(
                site_id="BS-TEST-003",
                name="Чужой объект",
                project_id=seeded["ucn_project_id"],
                region="Казань",
                status=SiteStatus.testing,
                contractor_id=other_contractor.id,
            )
        )
        await session.commit()

    headers = token_headers(seeded["contractor_user_id"], "contractor")
    resp = await client.get(
        f"/api/v1/reports/status_overview?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    summary = {item["label"]: item["value"] for item in data["summary"]}
    assert summary["Всего объектов"] == "1"


async def test_milestone_readiness_report_returns_ucn_specific_data(client, seeded, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with factory() as session:
        site = await session.get(Site, seeded["site_pk"])
        site.ams_permit_plan = now - timedelta(days=10)
        site.ams_permit_fact = now - timedelta(days=8)
        site.foundation_pour_plan = now - timedelta(days=4)
        site.foundation_pour_fact = None
        site.ams_installation_plan = now + timedelta(days=7)
        site.equipment_receipt_plan = now - timedelta(days=2)
        site.equipment_receipt_fact = None
        site.pnr_plan_stage = now + timedelta(days=14)
        await session.commit()

    headers = token_headers(seeded["manager_id"], "manager")
    resp = await client.get(
        f"/api/v1/reports/milestone_readiness?project_id={seeded['ucn_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "milestone_readiness"
    assert len(data["charts"]) == 2
    assert any(row["label"] == "Разрешение АМС" for row in data["charts"][0]["rows"])
    assert any(sheet["name"] == "Milestones" for sheet in data["export_sheets"])


async def test_placeholder_project_does_not_expose_report_detail(client, seeded):
    headers = token_headers(seeded["admin_id"], "admin")

    resp = await client.get(
        f"/api/v1/reports/status_overview?project_id={seeded['placeholder_project_id']}",
        headers=headers,
    )

    assert resp.status_code == 404
