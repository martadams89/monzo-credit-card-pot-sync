"""Add missing columns to users table

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2025-03-08 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5g6'
down_revision = 'a1b2c3d4e5f6'  # This should match the previous migration's revision ID
branch_labels = None
depends_on = None

def upgrade():
    # Add created_at column with default value
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP")
    
    # Add updated_at column with default value
    op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP")
    
    # Add last_login column (can be null)
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    
    # Add email_verified column if it doesn't exist yet
    try:
        op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='1'))
    except Exception:
        # Column might already exist
        pass

def downgrade():
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    # Don't drop email_verified as we're not sure if it existed before
