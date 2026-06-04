"""Update UCN template v2 headers

Revision ID: 007_update_ucn_template_v2_headers
Revises: 006_add_ucn_template_v2_fields
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "007_update_ucn_template_v2_headers"
down_revision = "006_add_ucn_template_v2_fields"
branch_labels = None
depends_on = None


NEW_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("ams_storage_city", sa.Text()),
    ("ams_verticality_report_plan", sa.DateTime(timezone=True)),
    ("ams_verticality_report_fact", sa.DateTime(timezone=True)),
    ("smr_order", sa.Text()),
    ("psez_preparation", sa.Text()),
    ("kzd_smr", sa.Text()),
]


def upgrade() -> None:
    for name, column_type in NEW_COLUMNS:
        op.add_column("sites", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(NEW_COLUMNS):
        op.drop_column("sites", name)
