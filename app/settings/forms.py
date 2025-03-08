"""Settings forms"""

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length

class EmailSettingsForm(FlaskForm):
    """Email settings form"""
    email_smtp_server = StringField('SMTP Server', validators=[DataRequired()])
    email_smtp_port = IntegerField('SMTP Port', validators=[DataRequired(), NumberRange(min=1, max=65535)])
    email_smtp_username = StringField('SMTP Username', validators=[DataRequired()])
    email_smtp_password = PasswordField('SMTP Password', validators=[DataRequired()])
    email_from_address = StringField('From Email Address', validators=[DataRequired(), Email()])
    email_use_tls = BooleanField('Use TLS')
    submit = SubmitField('Save Email Settings')
