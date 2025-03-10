from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, EmailField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp
import re
from app.models.user_repository import SqlAlchemyUserRepository
from app.extensions import db

user_repository = SqlAlchemyUserRepository(db)

class LoginForm(FlaskForm):
    """Form for user login."""
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64, message='Username must be between 3 and 64 characters'),
        Regexp(r'^[A-Za-z0-9_.-]+$', message="Username must contain only letters, numbers, dots, dashes and underscores.")
    ])
    email = EmailField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Sign Up')

    def validate_password(self, field):
        """Validate password complexity."""
        password = field.data
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must include at least one uppercase letter')
            
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must include at least one lowercase letter')
            
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must include at least one number')
            
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError('Password must include at least one special character')

    def validate_username(self, username):
        user = user_repository.get_by_username(username.data)
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = user_repository.get_by_email(email.data)
        if user is not None:
            raise ValidationError('Please use a different email address.')

class ResetPasswordRequestForm(FlaskForm):
    """Form for requesting a password reset."""
    email = EmailField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    """Form for resetting password."""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')
    
    def validate_password(self, field):
        """Validate password complexity."""
        password = field.data
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must include at least one uppercase letter')
            
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must include at least one lowercase letter')
            
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must include at least one number')
            
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError('Password must include at least one special character')

class TOTPSetupForm(FlaskForm):
    """Form for setting up TOTP-based 2FA."""
    token = StringField('Verification Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Verification code must be 6 digits')
    ])
    submit = SubmitField('Verify and Enable 2FA')

class TOTPVerifyForm(FlaskForm):
    """Form for verifying TOTP code during login."""
    token = StringField('Verification Code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Verification code must be 6 digits')
    ])
    submit = SubmitField('Verify')

class ChangePasswordForm(FlaskForm):
    """Form for changing password."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    new_password2 = PasswordField(
        'Repeat New Password', validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')]
    )
    submit = SubmitField('Change Password')
