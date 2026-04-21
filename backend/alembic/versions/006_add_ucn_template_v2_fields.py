"""Add fields for the new UCN 2.0 tracker template

Revision ID: 006_add_ucn_template_v2_fields
Revises: 005_add_projects
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "006_add_ucn_template_v2_fields"
down_revision = "005_add_projects"
branch_labels = None
depends_on = None


NEW_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("row_number", sa.Integer()),
    ("fias_code", sa.Text()),
    ("macroregion", sa.Text()),
    ("regional_branch", sa.Text()),
    ("district", sa.Text()),
    ("rural_settlement", sa.Text()),
    ("ams_permit_plan", sa.DateTime(timezone=True)),
    ("ams_permit_fact", sa.DateTime(timezone=True)),
    ("power_tu_received_date", sa.DateTime(timezone=True)),
    ("ves_tu_execution_plan", sa.DateTime(timezone=True)),
    ("ves_tu_execution_fact", sa.DateTime(timezone=True)),
    ("vols_ready_plan", sa.DateTime(timezone=True)),
    ("vols_ready_fact", sa.DateTime(timezone=True)),
    ("po", sa.Text()),
    ("igi_visit_plan", sa.DateTime(timezone=True)),
    ("igi_visit_fact", sa.DateTime(timezone=True)),
    ("igi_preparation_plan", sa.DateTime(timezone=True)),
    ("igi_preparation_fact", sa.DateTime(timezone=True)),
    ("igi_approval_plan", sa.DateTime(timezone=True)),
    ("igi_approval_fact", sa.DateTime(timezone=True)),
    ("ams_type", sa.Text()),
    ("pir_order", sa.Text()),
    ("foundation_pour_plan", sa.DateTime(timezone=True)),
    ("foundation_pour_fact", sa.DateTime(timezone=True)),
    ("ams_receipt_plan", sa.DateTime(timezone=True)),
    ("ams_receipt_fact", sa.DateTime(timezone=True)),
    ("ams_installation_plan", sa.DateTime(timezone=True)),
    ("ams_installation_fact", sa.DateTime(timezone=True)),
    ("ppo", sa.Text()),
    ("appi_kzh_preparation_plan", sa.DateTime(timezone=True)),
    ("appi_kzh_preparation_fact", sa.DateTime(timezone=True)),
    ("appi_kzh_approval_plan", sa.DateTime(timezone=True)),
    ("appi_kzh_approval_fact", sa.DateTime(timezone=True)),
    ("appi_ka_approval_plan", sa.DateTime(timezone=True)),
    ("appi_ka_approval_fact", sa.DateTime(timezone=True)),
    ("rd_release", sa.DateTime(timezone=True)),
    ("tu_es_signing", sa.DateTime(timezone=True)),
    ("es_tu_paper_submission", sa.DateTime(timezone=True)),
    ("rd_acceptance", sa.DateTime(timezone=True)),
    ("kzd_pir", sa.Text()),
    ("smr_order_signing", sa.DateTime(timezone=True)),
    ("bs_equipment_issuance", sa.DateTime(timezone=True)),
    ("requirement", sa.Text()),
    ("bs_trip", sa.Text()),
    ("equipment_receipt_plan", sa.DateTime(timezone=True)),
    ("equipment_receipt_fact", sa.DateTime(timezone=True)),
    ("brigade_contacts", sa.Text()),
    ("pnr_plan_stage", sa.DateTime(timezone=True)),
    ("pnr_fact_stage", sa.DateTime(timezone=True)),
    ("tu_completion_certificate", sa.DateTime(timezone=True)),
    ("passport_transfer_oge", sa.DateTime(timezone=True)),
    ("id_docs", sa.Text()),
    ("smr_order_status", sa.Text()),
]


def upgrade() -> None:
    for name, column_type in NEW_COLUMNS:
        op.add_column("sites", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(NEW_COLUMNS):
        op.drop_column("sites", name)
