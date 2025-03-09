"""Update schema with cooldown fields and name column

Revision ID: update_schema
Revises: add_name_to_accounts
Create Date: 2025-03-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'update_schema'
down_revision = 'add_name_to_accounts'

def upgrade():
    """Update database schema."""
    # Add cooldown fields to accounts if they don't exist
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        # Check if columns exist before adding
        conn = op.get_bind()
        columns = [c['name'] for c in conn.execute('PRAGMA table_info(accounts)').fetchall()]
        
        # Add cooldown fields if they don't exist
        if 'cooldown_until' not in columns:
            batch_op.add_column(sa.Column('cooldown_until', sa.Integer, nullable=True))
        if 'cooldown_ref_card_balance' not in columns:
            batch_op.add_column(sa.Column('cooldown_ref_card_balance', sa.Integer, nullable=True))
        if 'cooldown_ref_pot_balance' not in columns:
            batch_op.add_column(sa.Column('cooldown_ref_pot_balance', sa.Integer, nullable=True))
        if 'stable_pot_balance' not in columns:
            batch_op.add_column(sa.Column('stable_pot_balance', sa.Integer, nullable=True))

def downgrade():
    """Downgrade database schema."""
    # Remove cooldown fields
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('stable_pot_balance')
        batch_op.drop_column('cooldown_ref_pot_balance')
        batch_op.drop_column('cooldown_ref_card_balance')
        batch_op.drop_column('cooldown_until')
