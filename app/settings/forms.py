"""Forms for settings pages."""

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional

class EmailSettingsForm(FlaskForm):
    """Form for email settings."""
    smtp_server = StringField('SMTP Server', validators=[DataRequired()])
    smtp_port = IntegerField('SMTP Port', validators=[DataRequired(), NumberRange(min=1, max=65535)], default=587)
    smtp_username = StringField('SMTP Username', validators=[DataRequired()])
    smtp_password = PasswordField('SMTP Password', validators=[Optional()])
    smtp_use_tls = BooleanField('Use TLS')
    default_sender = StringField('Default Sender Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Save Settings')

class SyncSettingsForm(FlaskForm):
    """Form for sync settings."""
    enable_sync = BooleanField('Enable automatic synchronization')
    sync_interval = IntegerField('Sync Interval (hours)', 
                               validators=[NumberRange(min=1, max=24)],
                               default=2)
    enable_cooldown = BooleanField('Enable cooldown period')
    cooldown_hours = IntegerField('Cooldown Period (hours)',
                                validators=[NumberRange(min=1, max=24)],
                                default=3)
    threshold_percentage = IntegerField('Sync Threshold (%)',
                                       validators=[NumberRange(min=1, max=100)],
                                       default=5,
                                       description="Only sync if balance differs by more than this percentage")
    submit = SubmitField('Save Settings')

class AdminSettingsForm(FlaskForm):
    """Form for admin settings."""
    allow_registration = BooleanField('Allow New User Registration', default=True)
    admin_registration_code = StringField('Admin Registration Code', validators=[Optional()])
    submit = SubmitField('Save Settings')
    
    def validate_admin_registration_code(self, field):
        """Validate admin registration code format."""
        if field.data and len(field.data) < 8:
            raise ValidationError('Registration code must be at least 8 characters long.')

class BackupSettingsForm(FlaskForm):
    """Form for backup settings."""
    enable_backups = BooleanField('Enable Automated Backups', default=True)
    backup_retention_days = IntegerField('Backup Retention (days)', 
                                        validators=[NumberRange(min=1, max=90)],
                                        default=7)
    backup_schedule = StringField('Backup Schedule (cron format)', 
                                 validators=[DataRequired()],
                                 default='0 0 * * *')  # Daily at midnight
    backup_directory = StringField('Backup Directory', 
                                  validators=[DataRequired()],
                                  default='backups')
    submit = SubmitField('Save Settings')
    
    def validate_backup_schedule(self, field):
        """Validate cron expression format."""
        cron_pattern = r'^(\*|([0-9]|1[0-9]|2[0-9]|3[0-9]|4[0-9]|5[0-9])) (\*|([0-9]|1[0-9]|2[0-3])) (\*|([1-9]|1[0-9]|2[0-9]|3[0-1])) (\*|([1-9]|1[0-2])) (\*|([0-6]))$'
        if not re.match(cron_pattern, field.data):
            raise ValidationError('Invalid cron expression format.')

class ProfileForm(FlaskForm):
    """Form for user profile settings."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=64)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    submit = SubmitField('Save Profile')

class ChangePasswordForm(FlaskForm):
    """Form for changing password."""
    current_password = PasswordField('Current Password', validators=[
        DataRequired()
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

class AccountSettingsForm(FlaskForm):
    """Form for account settings."""
    name = StringField('Display Name', validators=[
        Optional(),
        Length(max=64)
    ])
    submit = SubmitField('Save Account Settings')

class NotificationSettingsForm(FlaskForm):
    """Form for notification settings."""
    email_enabled = BooleanField('Enable email notifications')
    notify_success = BooleanField('Notify on successful syncs')
    notify_error = BooleanField('Notify on failed syncs')
    notify_auth = BooleanField('Notify on authentication issues')
    submit = SubmitField('Save Notification Settings')
