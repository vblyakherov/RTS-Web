"""Add site_history table for field-level change tracking

Revision ID: 003_add_site_history
Revises: 002_add_contractors_regions
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '003_add_site_history'
down_revision = '002_add_contractors_regions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'site_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(128), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('sync_batch_id', sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_site_history_id', 'site_history', ['id'])
    op.create_index('ix_site_history_site_changed', 'site_history', ['site_id', 'changed_at'])
    op.create_index('ix_site_history_batch', 'site_history', ['sync_batch_id'])
    op.create_index('ix_site_history_field', 'site_history', ['site_id', 'field_name'])


def downgrade() -> None:
    op.drop_index('ix_site_history_field', table_name='site_history')
    op.drop_index('ix_site_history_batch', table_name='site_history')
    op.drop_index('ix_site_history_site_changed', table_name='site_history')
    op.drop_index('ix_site_history_id', table_name='site_history')
    op.drop_table('site_history')
