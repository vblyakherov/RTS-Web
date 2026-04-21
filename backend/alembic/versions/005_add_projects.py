"""Add projects architecture and assign current UCN data

Revision ID: 005_add_projects
Revises: 004_add_site_ni_fields
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = "005_add_projects"
down_revision = "004_add_site_ni_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_key", sa.String(length=64), nullable=False, server_default="placeholder"),
        sa.Column("template_key", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_projects_name"),
        sa.UniqueConstraint("code", name="uq_projects_code"),
    )
    op.create_index("ix_projects_id", "projects", ["id"], unique=False)
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)
    op.create_index("ix_projects_code", "projects", ["code"], unique=True)

    op.create_table(
        "user_projects",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "project_id"),
    )

    op.add_column("sites", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_sites_project_id",
        "sites",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sites_project_id", "sites", ["project_id"], unique=False)

    op.execute(
        """
        INSERT INTO projects (name, code, description, module_key, template_key, is_active, sort_order)
        VALUES
            (
                'УЦН 2.0 2026 год',
                'ucn-2026',
                'Текущий рабочий модуль стройки УЦН 2.0 с объектами, Excel import/export и XLSM sync.',
                'ucn_sites_v1',
                'sync_template.xlsm',
                true,
                10
            ),
            (
                'ТСПУ',
                'tspu',
                'Крупный проект добавлен как архитектурный контейнер. Внутренний формат пока не настроен.',
                'placeholder',
                NULL,
                true,
                20
            ),
            (
                'Стройка ЦОД',
                'dc-build',
                'Крупный проект добавлен как архитектурный контейнер. Внутренний формат пока не настроен.',
                'placeholder',
                NULL,
                true,
                30
            )
        """
    )

    op.execute(
        """
        UPDATE sites
        SET project_id = (
            SELECT id
            FROM projects
            WHERE code = 'ucn-2026'
        )
        WHERE project_id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO user_projects (user_id, project_id)
        SELECT users.id, projects.id
        FROM users
        CROSS JOIN projects
        WHERE projects.code = 'ucn-2026'
          AND users.role::text IN ('manager', 'viewer')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sites_project_id", table_name="sites")
    op.drop_constraint("fk_sites_project_id", "sites", type_="foreignkey")
    op.drop_column("sites", "project_id")

    op.drop_table("user_projects")

    op.drop_index("ix_projects_code", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")
