"""Forms for admin actions."""

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, ValidationError

class UserEditForm(FlaskForm):
    """Form for editing users."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=64)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    new_password = PasswordField('New Password', validators=[Optional()])
    is_admin = BooleanField('Administrator')
    is_active = BooleanField('Active')
    submit = SubmitField('Save Changes')

class SystemSettingForm(FlaskForm):
    """Form for editing system settings."""
    settings = TextAreaField('Settings JSON')
    submit = SubmitField('Save Settings')

class NewUserForm(FlaskForm):
    """Form for creating a new user."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=64)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    is_admin = BooleanField('Administrator')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Create User')
    
    def validate_username(self, username):
        """Validate username is unique."""
        from app.models.user import User
        
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
            
    def validate_email(self, email):
        """Validate email is unique."""
        from app.models.user import User
        
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email address already registered.')
