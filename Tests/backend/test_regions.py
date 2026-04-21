"""
test_regions.py - tests for region directory behavior.

Covered scenarios:
  - POST /regions persists even without dependency auto-commit
  - GET /regions does not overwrite manually managed is_active
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from conftest import token_headers
from app.models.region import Region


async def test_admin_can_create_region_without_dependency_autocommit(client_no_autocommit, seeded):
    """Region create must persist via explicit commit in the endpoint."""
    headers = token_headers(seeded["admin_id"], "admin")

    create_resp = await client_no_autocommit.post(
        "/api/v1/regions/",
        json={"name": "Ярославская область", "is_active": True},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    list_resp = await client_no_autocommit.get(
        "/api/v1/regions/?active_only=false",
        headers=headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    names = {item["name"] for item in list_resp.json()}
    assert "Ярославская область" in names


async def test_list_regions_does_not_override_manual_is_active(client, seeded, db_engine):
    """GET /regions must not deactivate a manually active region without sites."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        region = Region(name="Ручной регион", is_active=True)
        session.add(region)
        await session.commit()
        region_id = region.id

    headers = token_headers(seeded["admin_id"], "admin")
    list_resp = await client.get("/api/v1/regions/?active_only=false", headers=headers)
    assert list_resp.status_code == 200, list_resp.text

    async with factory() as session:
        saved = await session.scalar(select(Region).where(Region.id == region_id))

    assert saved is not None
    assert saved.is_active is True
