"""add_ai_accounts

Revision ID: 3a58f9d2a4e1
Revises: fe42f8daa968
Create Date: 2025-08-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a58f9d2a4e1'
down_revision = 'fe42f8daa968'
branch_labels = None
depends_on = None


def upgrade():
    # Create ai_accounts table
    op.create_table('ai_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('api_id', sa.String(), nullable=False),
        sa.Column('api_hash', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('session_string', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_accounts_id'), 'ai_accounts', ['id'], unique=False)


def downgrade():
    # Drop ai_accounts table
    op.drop_index(op.f('ix_ai_accounts_id'), table_name='ai_accounts')
    op.drop_table('ai_accounts')
