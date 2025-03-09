"""Forms for the dashboard."""

from flask_wtf import FlaskForm
from wtforms import SubmitField, BooleanField
from wtforms.validators import Optional

class SyncNowForm(FlaskForm):
    """Form for triggering an immediate sync."""
    force = BooleanField('Force sync (override cooldown)', default=False)
    submit = SubmitField('Sync Now')

class ManualSyncForm(FlaskForm):
    """Form for manual synchronization."""
    force = BooleanField('Force sync (override cooldown periods)')
    submit = SubmitField('Synchronize Now')

class SyncForm(FlaskForm):
    """Form for manual synchronization."""
    force = BooleanField('Force synchronization (ignore cooldown period)', validators=[Optional()])
    submit = SubmitField('Synchronize Now')
