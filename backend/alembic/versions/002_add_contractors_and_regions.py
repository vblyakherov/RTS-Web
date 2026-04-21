"""Add contractors and regions directories

Revision ID: 002_add_contractors_regions
Revises: 08554a11e51f
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_contractors_regions'
down_revision = '08554a11e51f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Таблица подрядчиков
    op.create_table(
        'contractors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('contact_person', sa.String(256), nullable=True),
        sa.Column('phone', sa.String(64), nullable=True),
        sa.Column('email', sa.String(128), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_contractors_name'),
    )
    op.create_index('ix_contractors_id', 'contractors', ['id'], unique=False)
    op.create_index('ix_contractors_name', 'contractors', ['name'], unique=True)

    # 2. Таблица регионов
    op.create_table(
        'regions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_regions_name'),
    )
    op.create_index('ix_regions_id', 'regions', ['id'], unique=False)
    op.create_index('ix_regions_name', 'regions', ['name'], unique=True)

    # 3. users.contractor_id → contractors (для пользователей с ролью contractor)
    op.add_column('users', sa.Column('contractor_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_contractor_id',
        'users', 'contractors',
        ['contractor_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_users_contractor_id', 'users', ['contractor_id'], unique=False)

    # 4. sites.region_id → regions
    op.add_column('sites', sa.Column('region_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sites_region_id',
        'sites', 'regions',
        ['region_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_sites_region_id', 'sites', ['region_id'], unique=False)

    # 5. Меняем sites.contractor_id: старый FK указывал на users, теперь на contractors
    #    Сначала обнуляем существующие значения (они ссылались на users, не на contractors)
    op.execute("UPDATE sites SET contractor_id = NULL")
    #    Удаляем старый FK-constraint
    op.drop_constraint('sites_contractor_id_fkey', 'sites', type_='foreignkey')
    #    Добавляем новый FK на contractors
    op.create_foreign_key(
        'fk_sites_contractor_id',
        'sites', 'contractors',
        ['contractor_id'], ['id'],
        ondelete='SET NULL',
    )

    # 6. sites.region теперь nullable (раньше NOT NULL)
    op.alter_column('sites', 'region', nullable=True)


def downgrade() -> None:
    op.alter_column('sites', 'region', nullable=False)

    op.drop_constraint('fk_sites_contractor_id', 'sites', type_='foreignkey')
    op.create_foreign_key(
        'sites_contractor_id_fkey',
        'sites', 'users',
        ['contractor_id'], ['id'],
        ondelete='SET NULL',
    )

    op.drop_index('ix_sites_region_id', 'sites')
    op.drop_constraint('fk_sites_region_id', 'sites', type_='foreignkey')
    op.drop_column('sites', 'region_id')

    op.drop_index('ix_users_contractor_id', 'users')
    op.drop_constraint('fk_users_contractor_id', 'users', type_='foreignkey')
    op.drop_column('users', 'contractor_id')

    op.drop_index('ix_regions_name', 'regions')
    op.drop_index('ix_regions_id', 'regions')
    op.drop_table('regions')

    op.drop_index('ix_contractors_name', 'contractors')
    op.drop_index('ix_contractors_id', 'contractors')
    op.drop_table('contractors')
