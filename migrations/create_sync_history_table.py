"""
Create sync history table
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'create_sync_history_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('sync_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True, default=datetime.utcnow),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('data', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('sync_history')
