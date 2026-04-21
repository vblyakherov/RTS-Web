from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.site import Site, SiteStatus


_STATUS_TEXT_CANCELLED = ("отмен", "cancel")
_STATUS_TEXT_ACCEPTED = ("принят", "заверш", "выполн", "сдан")
_STATUS_TEXT_CONSTRUCTION = ("в работе", "смр", "подпис", "заказ", "поставка")


def apply_template_derivations(
    payload: dict[str, Any],
    site: Site | None = None,
) -> dict[str, Any]:
    """
    Нормализует и достраивает базовые поля Site из данных нового UCN-шаблона.

    Excel хранит доменные колонки, а UI/поиск продолжают опираться на
    системные поля `name`, `address`, `status`, `region`, координаты и даты.
    """
    merged = _merge_site_state(site, payload)
    derived: dict[str, Any] = {}

    name = _clean_str(merged.get("name")) or _clean_str(merged.get("site_id"))
    region = _clean_str(merged.get("region"))
    address = _build_address(merged)
    status = _derive_status(merged)

    if name is not None:
        derived["name"] = name
    if region is not None:
        derived["region"] = region
    if "address" not in payload or address != _clean_str(site.address if site else None):
        derived["address"] = address
    derived["status"] = status

    payload.update(derived)
    return payload


def _merge_site_state(site: Site | None, payload: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if site is not None:
        for field_name in (
            "site_id",
            "name",
            "region",
            "address",
            "planned_start",
            "planned_end",
            "actual_start",
            "actual_end",
            "status",
            "district",
            "rural_settlement",
            "macroregion",
            "regional_branch",
            "latitude",
            "longitude",
            "igi_visit_fact",
            "igi_preparation_fact",
            "igi_approval_fact",
            "foundation_pour_fact",
            "ams_receipt_fact",
            "ams_installation_fact",
            "rd_release",
            "smr_order_signing",
            "equipment_receipt_fact",
            "pnr_fact_stage",
            "smr_order_status",
        ):
            if hasattr(site, field_name):
                merged[field_name] = getattr(site, field_name)

    merged.update(payload)
    return merged


def _build_address(values: Mapping[str, Any]) -> str | None:
    parts: list[str] = []
    for raw in (
        values.get("district"),
        values.get("rural_settlement"),
        values.get("name"),
        values.get("region"),
    ):
        value = _clean_str(raw)
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts) if parts else None


def _derive_status(values: Mapping[str, Any]) -> SiteStatus:
    status_text = _clean_str(values.get("smr_order_status"))
    if status_text and any(token in status_text.lower() for token in _STATUS_TEXT_CANCELLED):
        return SiteStatus.cancelled
    if status_text and any(token in status_text.lower() for token in _STATUS_TEXT_ACCEPTED):
        return SiteStatus.accepted

    if values.get("actual_end"):
        return SiteStatus.accepted
    if values.get("pnr_fact_stage"):
        return SiteStatus.testing
    if values.get("actual_start") or values.get("equipment_receipt_fact") or values.get("smr_order_signing"):
        return SiteStatus.construction
    if status_text and any(token in status_text.lower() for token in _STATUS_TEXT_CONSTRUCTION):
        return SiteStatus.construction
    if values.get("rd_release") or values.get("ams_installation_fact") or values.get("foundation_pour_fact"):
        return SiteStatus.design
    if values.get("igi_visit_fact") or values.get("igi_preparation_fact") or values.get("igi_approval_fact"):
        return SiteStatus.survey
    return SiteStatus.planned


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
