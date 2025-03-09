"""Add name column to accounts table

Revision ID: add_name_to_accounts
Revises: add_timestamp_to_settings
Create Date: 2025-03-09 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_name_to_accounts'
down_revision = 'add_timestamp_to_settings'  # Should reference the previous migration

def upgrade():
    """Add name column to accounts table."""
    # Add name column 
    op.add_column('accounts', sa.Column('name', sa.String(64), nullable=True))
    
    # Set default values based on account type
    op.execute("UPDATE accounts SET name = 'Monzo Account' WHERE type = 'monzo'")
    op.execute("UPDATE accounts SET name = 'Credit Card' WHERE type = 'credit_card'")

def downgrade():
    """Remove name column from accounts table."""
    op.drop_column('accounts', 'name')
