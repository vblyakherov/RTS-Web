from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportDefinitionOut(BaseModel):
    key: str
    title: str
    description: str
    available_formats: list[str] = Field(default_factory=lambda: ["pdf", "pptx", "xlsx"])


class ReportMetricOut(BaseModel):
    label: str
    value: str
    hint: str | None = None
    tone: str = "primary"


class ReportChartRowOut(BaseModel):
    label: str
    value: float
    display_value: str
    share: float | None = None
    hint: str | None = None
    tone: str = "primary"


class ReportChartOut(BaseModel):
    title: str
    description: str | None = None
    rows: list[ReportChartRowOut]


class ReportTableColumnOut(BaseModel):
    key: str
    label: str
    align: str = "start"


class ReportTableOut(BaseModel):
    title: str
    description: str | None = None
    columns: list[ReportTableColumnOut]
    rows: list[dict[str, Any]]


class ReportSheetOut(BaseModel):
    name: str
    columns: list[ReportTableColumnOut]
    rows: list[dict[str, Any]]


class ProjectReportOut(BaseModel):
    key: str
    title: str
    description: str
    project_name: str
    generated_at: datetime
    summary: list[ReportMetricOut]
    highlights: list[str]
    charts: list[ReportChartOut]
    tables: list[ReportTableOut]
    export_sheets: list[ReportSheetOut]
