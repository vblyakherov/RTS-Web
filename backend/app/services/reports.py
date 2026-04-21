from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.project import Project
from app.models.site import Site, SiteStatus


STATUS_META = {
    SiteStatus.planned: {"label": "Запланирован", "tone": "secondary"},
    SiteStatus.survey: {"label": "Обследование", "tone": "info"},
    SiteStatus.design: {"label": "Проектирование", "tone": "primary"},
    SiteStatus.permitting: {"label": "Разрешения", "tone": "warning"},
    SiteStatus.construction: {"label": "Строительство", "tone": "orange"},
    SiteStatus.testing: {"label": "Тестирование", "tone": "cyan"},
    SiteStatus.accepted: {"label": "Принят", "tone": "success"},
    SiteStatus.cancelled: {"label": "Отменён", "tone": "danger"},
}


UCN_REPORTS = [
    {
        "key": "status_overview",
        "title": "Статусный профиль проекта",
        "description": "Сводка по текущим статусам, принятым объектам и региональным зонам риска.",
    },
    {
        "key": "milestone_readiness",
        "title": "Готовность контрольных вех",
        "description": "UCN-отчет по ключевым серверным вехам: разрешение, фундамент, монтаж, оборудование и ПНР.",
    },
]


@dataclass(frozen=True)
class UcnMilestone:
    key: str
    label: str
    plan_field: str
    fact_field: str


UCN_MILESTONES = [
    UcnMilestone("ams_permit", "Разрешение АМС", "ams_permit_plan", "ams_permit_fact"),
    UcnMilestone("igi_approval", "Согласование ИГИ", "igi_approval_plan", "igi_approval_fact"),
    UcnMilestone("foundation_pour", "Заливка фундамента", "foundation_pour_plan", "foundation_pour_fact"),
    UcnMilestone("ams_installation", "Монтаж АМС", "ams_installation_plan", "ams_installation_fact"),
    UcnMilestone(
        "equipment_receipt",
        "Поставка оборудования",
        "equipment_receipt_plan",
        "equipment_receipt_fact",
    ),
    UcnMilestone("pnr", "ПНР", "pnr_plan_stage", "pnr_fact_stage"),
]


def get_report_definitions(project: Project) -> list[dict]:
    if project.module_key == "ucn_sites_v1":
        return UCN_REPORTS
    return []


def build_project_report(project: Project, report_key: str, sites: list[Site]) -> dict:
    if project.module_key != "ucn_sites_v1":
        raise KeyError(report_key)

    if report_key == "status_overview":
        return _build_status_overview(project, sites)
    if report_key == "milestone_readiness":
        return _build_milestone_readiness(project, sites)
    raise KeyError(report_key)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_delayed(site: Site, now: datetime) -> bool:
    if site.status in {SiteStatus.accepted, SiteStatus.cancelled}:
        return False
    planned_end = _as_utc(site.planned_end)
    return bool(planned_end and planned_end < now)


def _region_name(site: Site) -> str:
    region = site.region or getattr(site.region_rel, "name", None)
    return (region or "Без региона").strip()


def _fmt_int(value: int) -> str:
    return str(int(value))


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round((part / total) * 100, 1)


def _build_status_overview(project: Project, sites: list[Site]) -> dict:
    now = _now_utc()
    total_sites = len(sites)
    status_counts = Counter(site.status for site in sites)
    delayed_sites = sum(1 for site in sites if _is_delayed(site, now))
    accepted_sites = status_counts[SiteStatus.accepted]
    cancelled_sites = status_counts[SiteStatus.cancelled]
    active_sites = max(total_sites - accepted_sites - cancelled_sites, 0)
    completion_pct = _pct(accepted_sites, total_sites)

    status_rows = []
    for status, meta in STATUS_META.items():
        count = status_counts[status]
        status_rows.append(
            {
                "label": meta["label"],
                "value": float(count),
                "display_value": _fmt_int(count),
                "share": _pct(count, total_sites),
                "hint": f"{_pct(count, total_sites):.1f}% от проектного пула" if total_sites else "Нет объектов",
                "tone": meta["tone"],
            }
        )

    region_stats = defaultdict(lambda: {"region": "", "total": 0, "accepted": 0, "active": 0, "delayed": 0})
    for site in sites:
        region_name = _region_name(site)
        row = region_stats[region_name]
        row["region"] = region_name
        row["total"] += 1
        if site.status == SiteStatus.accepted:
            row["accepted"] += 1
        if site.status not in {SiteStatus.accepted, SiteStatus.cancelled}:
            row["active"] += 1
        if _is_delayed(site, now):
            row["delayed"] += 1

    region_rows = sorted(
        (
            {
                **row,
                "completion_pct": _fmt_pct(_pct(row["accepted"], row["total"])),
            }
            for row in region_stats.values()
        ),
        key=lambda row: (-row["delayed"], -row["total"], row["region"]),
    )

    delayed_regions = [row for row in region_rows if row["delayed"] > 0][:6]
    if not delayed_regions:
        delayed_regions = region_rows[:6]

    region_chart_rows = [
        {
            "label": row["region"],
            "value": float(row["delayed"]),
            "display_value": _fmt_int(row["delayed"]),
            "share": _pct(row["delayed"], max(delayed_sites, 1)),
            "hint": f"{row['total']} объектов, принято {row['accepted']}",
            "tone": "danger" if row["delayed"] else "success",
        }
        for row in delayed_regions
    ]

    most_loaded_status = max(status_rows, key=lambda row: row["value"], default=None)
    highlights = [
        f"Готовность по принятым объектам: {_fmt_pct(completion_pct)}.",
        (
            f"Самый насыщенный статус сейчас — {most_loaded_status['label']} "
            f"({_fmt_int(int(most_loaded_status['value']))} объектов)."
            if most_loaded_status and total_sites
            else "Проектный пул пока пуст."
        ),
        (
            f"Регионов с просрочкой: {sum(1 for row in region_rows if row['delayed'] > 0)}."
            if region_rows
            else "Региональная агрегация появится после загрузки объектов."
        ),
    ]

    summary = [
        {"label": "Всего объектов", "value": _fmt_int(total_sites), "hint": project.name, "tone": "dark"},
        {
            "label": "Принято",
            "value": _fmt_int(accepted_sites),
            "hint": _fmt_pct(completion_pct),
            "tone": "success",
        },
        {"label": "В работе", "value": _fmt_int(active_sites), "hint": "Без принятых и отменённых", "tone": "primary"},
        {"label": "Просрочено", "value": _fmt_int(delayed_sites), "hint": "По плановой дате окончания", "tone": "danger"},
    ]

    return {
        "key": "status_overview",
        "title": "Статусный профиль проекта",
        "description": "Визуальная сводка по текущим статусам, готовности и региональным точкам риска.",
        "project_name": project.name,
        "generated_at": now,
        "summary": summary,
        "highlights": highlights,
        "charts": [
            {
                "title": "Распределение по статусам",
                "description": "Показывает баланс проектного пула по основным этапам работ.",
                "rows": status_rows,
            },
            {
                "title": "Регионы с риском по срокам",
                "description": "Фокус на регионах, где уже накопилась просрочка по объектам.",
                "rows": region_chart_rows,
            },
        ],
        "tables": [
            {
                "title": "Региональная сводка",
                "description": "Агрегированные данные, на которых строится веб-отчет и выгрузки.",
                "columns": [
                    {"key": "region", "label": "Регион"},
                    {"key": "total", "label": "Объекты", "align": "end"},
                    {"key": "accepted", "label": "Принято", "align": "end"},
                    {"key": "active", "label": "В работе", "align": "end"},
                    {"key": "delayed", "label": "Просрочено", "align": "end"},
                    {"key": "completion_pct", "label": "Готовность", "align": "end"},
                ],
                "rows": region_rows,
            }
        ],
        "export_sheets": [
            {
                "name": "Summary",
                "columns": [
                    {"key": "label", "label": "Показатель"},
                    {"key": "value", "label": "Значение"},
                    {"key": "hint", "label": "Комментарий"},
                ],
                "rows": summary,
            },
            {
                "name": "Statuses",
                "columns": [
                    {"key": "label", "label": "Статус"},
                    {"key": "display_value", "label": "Объекты"},
                    {"key": "share", "label": "Доля, %"},
                    {"key": "hint", "label": "Комментарий"},
                ],
                "rows": status_rows,
            },
            {
                "name": "Regions",
                "columns": [
                    {"key": "region", "label": "Регион"},
                    {"key": "total", "label": "Объекты"},
                    {"key": "accepted", "label": "Принято"},
                    {"key": "active", "label": "В работе"},
                    {"key": "delayed", "label": "Просрочено"},
                    {"key": "completion_pct", "label": "Готовность"},
                ],
                "rows": region_rows,
            },
        ],
    }


def _build_milestone_readiness(project: Project, sites: list[Site]) -> dict:
    now = _now_utc()
    milestone_rows = []
    risk_rows = []
    tracked_points = 0
    completed_points = 0
    overdue_points = 0

    for milestone in UCN_MILESTONES:
        tracked = 0
        completed = 0
        overdue = 0
        for site in sites:
            plan_value = _as_utc(getattr(site, milestone.plan_field, None))
            fact_value = _as_utc(getattr(site, milestone.fact_field, None))
            if plan_value or fact_value:
                tracked += 1
            if fact_value:
                completed += 1
            if plan_value and not fact_value and plan_value < now:
                overdue += 1

        tracked_points += tracked
        completed_points += completed
        overdue_points += overdue
        completion_pct = _pct(completed, tracked)
        milestone_rows.append(
            {
                "label": milestone.label,
                "tracked_sites": tracked,
                "completed": completed,
                "overdue": overdue,
                "completion_pct": _fmt_pct(completion_pct),
                "value": float(completed),
                "display_value": _fmt_pct(completion_pct),
                "share": completion_pct,
                "hint": f"В работе на {tracked} объектах, просрочено {overdue}",
                "tone": "danger" if overdue else ("success" if completion_pct >= 75 else "warning"),
            }
        )

    for site in sites:
        overdue_labels = []
        for milestone in UCN_MILESTONES:
            plan_value = _as_utc(getattr(site, milestone.plan_field, None))
            fact_value = _as_utc(getattr(site, milestone.fact_field, None))
            if plan_value and not fact_value and plan_value < now:
                overdue_labels.append(milestone.label)
        if overdue_labels:
            risk_rows.append(
                {
                    "site_id": site.site_id,
                    "name": site.name,
                    "region": _region_name(site),
                    "overdue_count": len(overdue_labels),
                    "milestones": ", ".join(overdue_labels),
                }
            )

    risk_rows.sort(key=lambda row: (-row["overdue_count"], row["site_id"]))
    risk_chart_base = max((row["overdue_count"] for row in risk_rows), default=0)
    risk_chart_rows = [
        {
            "label": row["site_id"],
            "value": float(row["overdue_count"]),
            "display_value": _fmt_int(row["overdue_count"]),
            "share": _pct(row["overdue_count"], risk_chart_base or 1),
            "hint": row["milestones"],
            "tone": "danger",
        }
        for row in risk_rows[:8]
    ]

    objects_with_risk = len(risk_rows)
    overall_completion = _pct(completed_points, tracked_points)
    strongest_milestone = max(milestone_rows, key=lambda row: row["share"], default=None)
    weakest_milestone = max(milestone_rows, key=lambda row: row["overdue"], default=None)

    summary = [
        {"label": "Всего объектов", "value": _fmt_int(len(sites)), "hint": project.name, "tone": "dark"},
        {"label": "Контрольных вех", "value": _fmt_int(tracked_points), "hint": "План или факт заполнен", "tone": "primary"},
        {
            "label": "Выполнено",
            "value": _fmt_int(completed_points),
            "hint": _fmt_pct(overall_completion),
            "tone": "success",
        },
        {
            "label": "Просроченные вехи",
            "value": _fmt_int(overdue_points),
            "hint": f"Риск на {objects_with_risk} объектах",
            "tone": "danger",
        },
    ]

    highlights = [
        (
            f"Лучшая динамика сейчас у вехи «{strongest_milestone['label']}» "
            f"с готовностью {strongest_milestone['display_value']}."
            if strongest_milestone and tracked_points
            else "Вехи появятся после заполнения плановых и фактических дат."
        ),
        (
            f"Основной источник риска — «{weakest_milestone['label']}», "
            f"просрочено {weakest_milestone['overdue']}."
            if weakest_milestone and weakest_milestone["overdue"]
            else "Критичных просроченных вех сейчас не обнаружено."
        ),
        f"Общая готовность контрольных вех: {_fmt_pct(overall_completion)}.",
    ]

    return {
        "key": "milestone_readiness",
        "title": "Готовность контрольных вех",
        "description": "UCN-отчет по ключевым инженерным и строительно-монтажным вехам.",
        "project_name": project.name,
        "generated_at": now,
        "summary": summary,
        "highlights": highlights,
        "charts": [
            {
                "title": "Прогресс по ключевым вехам",
                "description": "Сопоставляет количество закрытых точек с плановым контуром UCN.",
                "rows": milestone_rows,
            },
            {
                "title": "Объекты с максимальным риском",
                "description": "Точки, где накапливается сразу несколько просроченных вех.",
                "rows": risk_chart_rows,
            },
        ],
        "tables": [
            {
                "title": "Матрица вех",
                "description": "Агрегированные показатели по каждой ключевой UCN-вехе.",
                "columns": [
                    {"key": "label", "label": "Веха"},
                    {"key": "tracked_sites", "label": "Объекты", "align": "end"},
                    {"key": "completed", "label": "Закрыто", "align": "end"},
                    {"key": "overdue", "label": "Просрочено", "align": "end"},
                    {"key": "completion_pct", "label": "Готовность", "align": "end"},
                ],
                "rows": milestone_rows,
            },
            {
                "title": "Список риск-объектов",
                "description": "Подходит для адресной работы с подрядчиками и региональными командами.",
                "columns": [
                    {"key": "site_id", "label": "ID объекта"},
                    {"key": "name", "label": "НП"},
                    {"key": "region", "label": "Регион"},
                    {"key": "overdue_count", "label": "Просрочено", "align": "end"},
                    {"key": "milestones", "label": "Критичные вехи"},
                ],
                "rows": risk_rows,
            },
        ],
        "export_sheets": [
            {
                "name": "Summary",
                "columns": [
                    {"key": "label", "label": "Показатель"},
                    {"key": "value", "label": "Значение"},
                    {"key": "hint", "label": "Комментарий"},
                ],
                "rows": summary,
            },
            {
                "name": "Milestones",
                "columns": [
                    {"key": "label", "label": "Веха"},
                    {"key": "tracked_sites", "label": "Объекты"},
                    {"key": "completed", "label": "Закрыто"},
                    {"key": "overdue", "label": "Просрочено"},
                    {"key": "completion_pct", "label": "Готовность"},
                ],
                "rows": milestone_rows,
            },
            {
                "name": "RiskSites",
                "columns": [
                    {"key": "site_id", "label": "ID объекта"},
                    {"key": "name", "label": "НП"},
                    {"key": "region", "label": "Регион"},
                    {"key": "overdue_count", "label": "Просрочено"},
                    {"key": "milestones", "label": "Критичные вехи"},
                ],
                "rows": risk_rows,
            },
        ],
    }
