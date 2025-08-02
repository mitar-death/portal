"""Update user id to bigint

Revision ID: a02cb5dec7a1
Revises: 88528ab49fea
Create Date: 2025-08-02 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a02cb5dec7a1'
down_revision: Union[str, None] = '88528ab49fea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert user.id column to BIGINT and update all foreign key references."""
    
    # First, remove foreign key constraints that reference users.id
    op.drop_constraint('active_sessions_user_id_fkey', 'active_sessions', type_='foreignkey')
    op.drop_constraint('ai_accounts_user_id_fkey', 'ai_accounts', type_='foreignkey')
    op.drop_constraint('groups_user_id_fkey', 'groups', type_='foreignkey')
    op.drop_constraint('keywords_user_id_fkey', 'keywords', type_='foreignkey')
    op.drop_constraint('selected_groups_user_id_fkey', 'selected_groups', type_='foreignkey')
    
    # Alter user_id columns in related tables to BIGINT
    op.alter_column('active_sessions', 'user_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    op.alter_column('ai_accounts', 'user_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    op.alter_column('groups', 'user_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    op.alter_column('keywords', 'user_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    op.alter_column('selected_groups', 'user_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    
    # Change the primary key column type
    op.alter_column('users', 'id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
    
    # Re-create foreign key constraints
    op.create_foreign_key('active_sessions_user_id_fkey', 'active_sessions', 'users', ['user_id'], ['id'])
    op.create_foreign_key('ai_accounts_user_id_fkey', 'ai_accounts', 'users', ['user_id'], ['id'])
    op.create_foreign_key('groups_user_id_fkey', 'groups', 'users', ['user_id'], ['id'])
    op.create_foreign_key('keywords_user_id_fkey', 'keywords', 'users', ['user_id'], ['id'])
    op.create_foreign_key('selected_groups_user_id_fkey', 'selected_groups', 'users', ['user_id'], ['id'])
    
    # Fix for group_ai_accounts table references if it exists
    from sqlalchemy import text
    connection = op.get_bind()
    result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    tables = [row[0] for row in result]
    
    if 'group_ai_accounts' in tables:
        op.drop_constraint('group_ai_accounts_group_id_fkey', 'group_ai_accounts', type_='foreignkey')
        op.alter_column('group_ai_accounts', 'group_id', existing_type=sa.INTEGER(), type_=sa.BIGINT())
        op.create_foreign_key('group_ai_accounts_group_id_fkey', 'group_ai_accounts', 'groups', ['group_id'], ['id'])


def downgrade() -> None:
    """Revert changes (note: this may fail if values exceed INTEGER range)."""
    # First, remove foreign key constraints that reference users.id
    op.drop_constraint('active_sessions_user_id_fkey', 'active_sessions', type_='foreignkey')
    op.drop_constraint('ai_accounts_user_id_fkey', 'ai_accounts', type_='foreignkey')
    op.drop_constraint('groups_user_id_fkey', 'groups', type_='foreignkey')
    op.drop_constraint('keywords_user_id_fkey', 'keywords', type_='foreignkey')
    op.drop_constraint('selected_groups_user_id_fkey', 'selected_groups', type_='foreignkey')
    
    # Alter user_id columns in related tables back to INTEGER
    op.alter_column('active_sessions', 'user_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    op.alter_column('ai_accounts', 'user_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    op.alter_column('groups', 'user_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    op.alter_column('keywords', 'user_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    op.alter_column('selected_groups', 'user_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    
    # Change the primary key column type back
    op.alter_column('users', 'id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
    
    # Re-create foreign key constraints
    op.create_foreign_key('active_sessions_user_id_fkey', 'active_sessions', 'users', ['user_id'], ['id'])
    op.create_foreign_key('ai_accounts_user_id_fkey', 'ai_accounts', 'users', ['user_id'], ['id'])
    op.create_foreign_key('groups_user_id_fkey', 'groups', 'users', ['user_id'], ['id'])
    op.create_foreign_key('keywords_user_id_fkey', 'keywords', 'users', ['user_id'], ['id'])
    op.create_foreign_key('selected_groups_user_id_fkey', 'selected_groups', 'users', ['user_id'], ['id'])
    
    # Fix for group_ai_accounts table references if it exists
    from sqlalchemy import text
    connection = op.get_bind()
    result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    tables = [row[0] for row in result]
    
    if 'group_ai_accounts' in tables:
        op.drop_constraint('group_ai_accounts_group_id_fkey', 'group_ai_accounts', type_='foreignkey')
        op.alter_column('group_ai_accounts', 'group_id', existing_type=sa.BIGINT(), type_=sa.INTEGER())
        op.create_foreign_key('group_ai_accounts_group_id_fkey', 'group_ai_accounts', 'groups', ['group_id'], ['id'])
