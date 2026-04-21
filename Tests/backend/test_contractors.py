"""
test_contractors.py - tests for contractor directory behavior.

Covered scenarios:
  - POST /contractors persists even without dependency auto-commit
  - GET /contractors does not overwrite manually managed is_active
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from conftest import token_headers
from app.models.contractor import Contractor


async def test_admin_can_create_contractor_without_dependency_autocommit(client_no_autocommit, seeded):
    """Contractor create must persist via explicit commit in the endpoint."""
    headers = token_headers(seeded["admin_id"], "admin")

    create_resp = await client_no_autocommit.post(
        "/api/v1/contractors/",
        json={"name": "ООО Новый подрядчик", "is_active": True},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    list_resp = await client_no_autocommit.get(
        "/api/v1/contractors/?active_only=false",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    names = {item["name"] for item in list_resp.json()}
    assert "ООО Новый подрядчик" in names


async def test_list_contractors_does_not_override_manual_is_active(client, seeded, db_engine):
    """GET /contractors must not deactivate a manually active contractor without sites."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        contractor = Contractor(name="ООО Ручной подрядчик", is_active=True)
        session.add(contractor)
        await session.commit()
        contractor_id = contractor.id

    headers = token_headers(seeded["admin_id"], "admin")
    list_resp = await client.get("/api/v1/contractors/?active_only=false", headers=headers)
    assert list_resp.status_code == 200, list_resp.text

    async with factory() as session:
        saved = await session.scalar(select(Contractor).where(Contractor.id == contractor_id))

    assert saved is not None
    assert saved.is_active is True
