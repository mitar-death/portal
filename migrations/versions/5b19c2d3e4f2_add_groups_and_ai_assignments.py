"""add_groups_and_ai_assignments

Revision ID: 5b19c2d3e4f2
Revises: 3a58f9d2a4e1
Create Date: 2025-08-02 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5b19c2d3e4f2'
down_revision = '3a58f9d2a4e1'
branch_labels = None
depends_on = None


def upgrade():
    # Create groups table
    op.create_table('groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('telegram_id', sa.BIGINT(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('member_count', sa.Integer(), default=0),
        sa.Column('is_channel', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_groups_id'), 'groups', ['id'], unique=False)
    op.create_index(op.f('ix_groups_telegram_id'), 'groups', ['telegram_id'], unique=False)

    # Create group_ai_accounts association table
    op.create_table('group_ai_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('ai_account_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
        sa.ForeignKeyConstraint(['ai_account_id'], ['ai_accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_group_ai_accounts_id'), 'group_ai_accounts', ['id'], unique=False)


def downgrade():
    # Drop group_ai_accounts table
    op.drop_index(op.f('ix_group_ai_accounts_id'), table_name='group_ai_accounts')
    op.drop_table('group_ai_accounts')
    
    # Drop groups table
    op.drop_index(op.f('ix_groups_telegram_id'), table_name='groups')
    op.drop_index(op.f('ix_groups_id'), table_name='groups')
    op.drop_table('groups')
