"""Add is_active column to users table

Revision ID: a1b2c3d4e5f6
Revises: previous_revision_id
Create Date: 2025-03-08 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None  # Replace with actual previous migration ID if it exists
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('users', 'is_active')
