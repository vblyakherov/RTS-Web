"""Initial schema

Revision ID: 08554a11e51f
Revises:
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "08554a11e51f"
down_revision = None
branch_labels = None
depends_on = None


user_role = sa.Enum("admin", "manager", "contractor", "viewer", name="user_role")
site_status = sa.Enum(
    "planned",
    "survey",
    "design",
    "permitting",
    "construction",
    "testing",
    "accepted",
    "cancelled",
    name="site_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    site_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("full_name", sa.String(length=256), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("status", site_status, nullable=False, server_default="planned"),
        sa.Column("contractor_id", sa.Integer(), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["contractor_id"],
            ["users.id"],
            name="sites_contractor_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id"),
    )
    op.create_index("ix_sites_id", "sites", ["id"], unique=False)
    op.create_index("ix_sites_site_id", "sites", ["site_id"], unique=True)
    op.create_index("ix_sites_region", "sites", ["region"], unique=False)
    op.create_index("ix_sites_status", "sites", ["status"], unique=False)
    op.create_index("ix_sites_contractor_id", "sites", ["contractor_id"], unique=False)

    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_logs_id", "action_logs", ["id"], unique=False)
    op.create_index("ix_action_logs_user_id", "action_logs", ["user_id"], unique=False)
    op.create_index("ix_action_logs_site_id", "action_logs", ["site_id"], unique=False)
    op.create_index("ix_action_logs_action", "action_logs", ["action"], unique=False)
    op.create_index("ix_action_logs_created_at", "action_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_action_logs_created_at", table_name="action_logs")
    op.drop_index("ix_action_logs_action", table_name="action_logs")
    op.drop_index("ix_action_logs_site_id", table_name="action_logs")
    op.drop_index("ix_action_logs_user_id", table_name="action_logs")
    op.drop_index("ix_action_logs_id", table_name="action_logs")
    op.drop_table("action_logs")

    op.drop_index("ix_sites_contractor_id", table_name="sites")
    op.drop_index("ix_sites_status", table_name="sites")
    op.drop_index("ix_sites_region", table_name="sites")
    op.drop_index("ix_sites_site_id", table_name="sites")
    op.drop_index("ix_sites_id", table_name="sites")
    op.drop_table("sites")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    site_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
