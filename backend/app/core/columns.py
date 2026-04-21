"""
Реестр колонок Excel-шаблона UCN 2.0.

Новый шаблон хранит данные объектов в плоской таблице и используется как
единый контракт для:
- `/api/v1/excel/import`
- `/api/v1/excel/export`
- `/api/v1/sync`
- истории изменений Excel-полей

Важно:
- ключ синхронизации — `ID объекта` (`site_id`);
- часть колонок маппится в базовые поля `Site` (`name`, `region`,
  `latitude`, `longitude`, `planned_start`, `actual_start`,
  `planned_end`, `actual_end`);
- остальные поля живут как template-specific колонки модели `Site`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text


@dataclass(frozen=True)
class ColumnDef:
    db_name: str
    excel_header: str
    python_type: type
    sa_type: Any
    nullable: bool = True
    is_key: bool = False
    group: str = ""
    excel_width: int = 18


SYNC_KEY_COLUMN = ColumnDef(
    db_name="site_id",
    excel_header="ID объекта",
    python_type=str,
    sa_type=String(length=64),
    nullable=False,
    is_key=True,
    group="Системные поля",
    excel_width=18,
)


SITE_COLUMNS: list[ColumnDef] = [
    ColumnDef("row_number", "№ п/п", int, Integer(), group="Локация", excel_width=10),
    ColumnDef("fias_code", "ФИАС код", str, Text(), group="Локация", excel_width=24),
    ColumnDef("macroregion", "Макрорегион", str, Text(), group="Локация", excel_width=20),
    ColumnDef("region", "Регион", str, Text(), group="Локация", excel_width=24),
    ColumnDef("regional_branch", "Региональный филиал", str, Text(), group="Локация", excel_width=24),
    ColumnDef("district", "Район", str, Text(), group="Локация", excel_width=28),
    ColumnDef("rural_settlement", "Сельское поселение", str, Text(), group="Локация", excel_width=28),
    ColumnDef("name", "Наименование НП", str, Text(), group="Локация", excel_width=28),
    ColumnDef("latitude", "WGS широта, гг", float, Float(), group="Координаты", excel_width=14),
    ColumnDef("longitude", "WGS долгота, гг", float, Float(), group="Координаты", excel_width=14),
    ColumnDef(
        "ams_permit_plan",
        "Дата получения разрешения на размещение АМС БС, план",
        datetime,
        DateTime(timezone=True),
        group="Разрешения",
        excel_width=18,
    ),
    ColumnDef(
        "ams_permit_fact",
        "Дата получения разрешения на размещение АМС БС, факт",
        datetime,
        DateTime(timezone=True),
        group="Разрешения",
        excel_width=18,
    ),
    ColumnDef(
        "power_tu_received_date",
        "ТУ на электропитание получены, дата",
        datetime,
        DateTime(timezone=True),
        group="Электропитание и ВОЛС",
        excel_width=18,
    ),
    ColumnDef(
        "ves_tu_execution_plan",
        "Дата выполнения ТУ ВЭС, план",
        datetime,
        DateTime(timezone=True),
        group="Электропитание и ВОЛС",
        excel_width=18,
    ),
    ColumnDef(
        "ves_tu_execution_fact",
        "Дата выполнения ТУ ВЭС, факт",
        datetime,
        DateTime(timezone=True),
        group="Электропитание и ВОЛС",
        excel_width=18,
    ),
    ColumnDef(
        "vols_ready_plan",
        "Дата готовности ВОЛС, план",
        datetime,
        DateTime(timezone=True),
        group="Электропитание и ВОЛС",
        excel_width=18,
    ),
    ColumnDef(
        "vols_ready_fact",
        "Дата готовности ВОЛС, факт",
        datetime,
        DateTime(timezone=True),
        group="Электропитание и ВОЛС",
        excel_width=18,
    ),
    ColumnDef("po", "ПО", str, Text(), group="Проектирование", excel_width=18),
    ColumnDef(
        "igi_visit_plan",
        "Выезд на обследование для подготовки ИГИ, план",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef(
        "igi_visit_fact",
        "Выезд на обследование для подготовки ИГИ, факт",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef(
        "igi_preparation_plan",
        "Подготовка ИГИ, план",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef(
        "igi_preparation_fact",
        "Подготовка ИГИ, факт",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef(
        "igi_approval_plan",
        "Согласование ИГИ, план",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef(
        "igi_approval_fact",
        "Согласование ИГИ, факт",
        datetime,
        DateTime(timezone=True),
        group="ИГИ",
        excel_width=18,
    ),
    ColumnDef("ams_type", "Тип АМС", str, Text(), group="АМС", excel_width=18),
    ColumnDef("pir_order", "Заказ ПИР", str, Text(), group="ПИР", excel_width=22),
    ColumnDef(
        "foundation_pour_plan",
        "Заливка фундамента, план",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef(
        "foundation_pour_fact",
        "Заливка фундамента, факт",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef(
        "ams_receipt_plan",
        "Получение АМС, план",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef(
        "ams_receipt_fact",
        "Получение АМС, факт",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef(
        "ams_installation_plan",
        "Установка АМС, план",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef(
        "ams_installation_fact",
        "Установка АМС, факт",
        datetime,
        DateTime(timezone=True),
        group="АМС",
        excel_width=18,
    ),
    ColumnDef("ppo", "ППО", str, Text(), group="Проектирование", excel_width=18),
    ColumnDef(
        "appi_kzh_preparation_plan",
        "Подготовка АППИ, КЖ, план",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КЖ",
        excel_width=18,
    ),
    ColumnDef(
        "appi_kzh_preparation_fact",
        "Подготовка АППИ, КЖ, факт",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КЖ",
        excel_width=18,
    ),
    ColumnDef(
        "appi_kzh_approval_plan",
        "Согласование АППИ, КЖ, план",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КЖ",
        excel_width=18,
    ),
    ColumnDef(
        "appi_kzh_approval_fact",
        "Согласование АППИ, КЖ, факт",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КЖ",
        excel_width=18,
    ),
    ColumnDef(
        "appi_ka_approval_plan",
        "Согласование АППИ КА, план",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КА",
        excel_width=18,
    ),
    ColumnDef(
        "appi_ka_approval_fact",
        "Согласование АППИ КА, факт",
        datetime,
        DateTime(timezone=True),
        group="АППИ и КА",
        excel_width=18,
    ),
    ColumnDef("rd_release", "Выпуск РД ", datetime, DateTime(timezone=True), group="РД и документы", excel_width=18),
    ColumnDef("tu_es_signing", "Подписание ТУ/ЭС ", datetime, DateTime(timezone=True), group="РД и документы", excel_width=18),
    ColumnDef(
        "es_tu_paper_submission",
        "Сдача ЭС и ТУ в бумаге ",
        datetime,
        DateTime(timezone=True),
        group="РД и документы",
        excel_width=18,
    ),
    ColumnDef("rd_acceptance", "Приемка РД", datetime, DateTime(timezone=True), group="РД и документы", excel_width=18),
    ColumnDef("kzd_pir", "КЗД на ПИР", str, Text(), group="ПИР", excel_width=18),
    ColumnDef(
        "smr_order_signing",
        "Подписание заказа на СМР",
        datetime,
        DateTime(timezone=True),
        group="СМР",
        excel_width=18,
    ),
    ColumnDef(
        "bs_equipment_issuance",
        "Выписка оборудования БС ",
        datetime,
        DateTime(timezone=True),
        group="Оборудование",
        excel_width=18,
    ),
    ColumnDef("requirement", "Требование ", str, Text(), group="Оборудование", excel_width=20),
    ColumnDef("bs_trip", "Рейс БС", str, Text(), group="Оборудование", excel_width=18),
    ColumnDef(
        "equipment_receipt_plan",
        "Получение оборудования, план",
        datetime,
        DateTime(timezone=True),
        group="Оборудование",
        excel_width=18,
    ),
    ColumnDef(
        "equipment_receipt_fact",
        "Получение оборудования, факт",
        datetime,
        DateTime(timezone=True),
        group="Оборудование",
        excel_width=18,
    ),
    ColumnDef("brigade_contacts", "Контакты бригады", str, Text(), group="СМР", excel_width=24),
    ColumnDef("planned_start", "Начало СМР, план", datetime, DateTime(timezone=True), group="СМР", excel_width=18),
    ColumnDef("actual_start", "Начало СМР, факт", datetime, DateTime(timezone=True), group="СМР", excel_width=18),
    ColumnDef("pnr_plan_stage", "ПНР, план", datetime, DateTime(timezone=True), group="ПНР и приемка", excel_width=18),
    ColumnDef("pnr_fact_stage", "ПНР, факт", datetime, DateTime(timezone=True), group="ПНР и приемка", excel_width=18),
    ColumnDef("planned_end", "Приемка, план", datetime, DateTime(timezone=True), group="ПНР и приемка", excel_width=18),
    ColumnDef("actual_end", "Приемка, факт", datetime, DateTime(timezone=True), group="ПНР и приемка", excel_width=18),
    ColumnDef(
        "tu_completion_certificate",
        "Справка о выполнении ТУ ",
        datetime,
        DateTime(timezone=True),
        group="Закрывающие документы",
        excel_width=18,
    ),
    ColumnDef(
        "passport_transfer_oge",
        "Передача Паспорта/АРБП/Справки о выполнении ТУ в ОГЭ ",
        datetime,
        DateTime(timezone=True),
        group="Закрывающие документы",
        excel_width=22,
    ),
    ColumnDef("id_docs", "ИД ", str, Text(), group="Закрывающие документы", excel_width=18),
    ColumnDef("smr_order_status", "Статус заказа на СМР", str, Text(), group="СМР", excel_width=24),
]


def normalize_excel_header(header: str | None) -> str:
    if header is None:
        return ""
    return str(header).strip()


def get_column_by_db_name(name: str) -> ColumnDef | None:
    return _by_db_name.get(name)


def get_column_by_header(header: str) -> ColumnDef | None:
    return _by_header.get(normalize_excel_header(header))


def get_syncable_db_names() -> list[str]:
    return [c.db_name for c in SITE_COLUMNS if not c.is_key]


def get_all_db_names() -> list[str]:
    return [c.db_name for c in SITE_COLUMNS]


def get_sync_excel_columns() -> list[ColumnDef]:
    return [SYNC_KEY_COLUMN, *SITE_COLUMNS]


def header_to_db_map() -> dict[str, str]:
    return {normalize_excel_header(c.excel_header): c.db_name for c in SITE_COLUMNS}


def db_to_header_map() -> dict[str, str]:
    return {c.db_name: c.excel_header for c in SITE_COLUMNS}


_by_db_name: dict[str, ColumnDef] = {c.db_name: c for c in SITE_COLUMNS}
_by_header: dict[str, ColumnDef] = {
    normalize_excel_header(c.excel_header): c
    for c in SITE_COLUMNS
}
