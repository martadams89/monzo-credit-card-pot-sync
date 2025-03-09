"""Add timestamp columns to settings table

Revision ID: add_timestamp_to_settings
Revises: REPLACE_WITH_PREVIOUS_REVISION
Create Date: 2025-03-09 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_timestamp_to_settings'
down_revision = None  # Set to the previous revision ID when running migrations

def upgrade():
    """Add timestamp columns to settings table."""
    # Add created_at column with a default value
    op.add_column('settings', sa.Column('created_at', sa.DateTime, nullable=True))
    op.execute("UPDATE settings SET created_at = CURRENT_TIMESTAMP")
    
    # Add updated_at column with a default value
    op.add_column('settings', sa.Column('updated_at', sa.DateTime, nullable=True))
    op.execute("UPDATE settings SET updated_at = CURRENT_TIMESTAMP")

def downgrade():
    """Remove timestamp columns from settings table."""
    op.drop_column('settings', 'updated_at')
    op.drop_column('settings', 'created_at')
