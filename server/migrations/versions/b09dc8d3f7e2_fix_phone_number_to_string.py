"""Fix phone number to string

Revision ID: b09dc8d3f7e2
Revises: a02cb5dec7a1
Create Date: 2025-08-02 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b09dc8d3f7e2'
down_revision: Union[str, None] = 'a02cb5dec7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert user.phone_number column to String."""
    
    # Create a temporary column with the new type
    op.add_column('users', sa.Column('phone_number_str', sa.String(), nullable=True))
    
    # Copy the data from the old column to the new one
    from sqlalchemy import text
    connection = op.get_bind()
    
    # Convert BIGINT to string
    connection.execute(text("UPDATE users SET phone_number_str = phone_number::text"))
    
    # Drop the old column
    op.drop_column('users', 'phone_number')
    
    # Rename the new column to the original name
    op.alter_column('users', 'phone_number_str', new_column_name='phone_number')
    
    # Create the index and unique constraint
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)


def downgrade() -> None:
    """Convert user.phone_number column back to BIGINT."""
    
    # Create a temporary column with the old type
    op.add_column('users', sa.Column('phone_number_big', sa.BIGINT(), nullable=True))
    
    # Copy the data from the string column to the BIGINT one, handling conversion errors
    from sqlalchemy import text
    connection = op.get_bind()
    
    # Convert string to BIGINT, handling possible errors
    connection.execute(text("UPDATE users SET phone_number_big = CASE WHEN phone_number ~ '^[0-9]+$' THEN phone_number::bigint ELSE NULL END"))
    
    # Drop the string column
    op.drop_column('users', 'phone_number')
    
    # Rename the BIGINT column to the original name
    op.alter_column('users', 'phone_number_big', new_column_name='phone_number')
    
    # Create the index and unique constraint
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)
