import uuid
import secrets
from datetime import datetime, timedelta
from enum import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager

class Role(Enum):
    USER = "user"
    ADMIN = "admin"

class User(db.Model, UserMixin):
    """User model for authentication and profile management."""
    
    __tablename__ = "user"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default=Role.USER.value)
    is_active = db.Column(db.Boolean, default=True)
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(36), unique=True, nullable=True)
    password_reset_token = db.Column(db.String(36), unique=True, nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(32), nullable=True)
    is_totp_enabled = db.Column(db.Boolean, default=False)
    is_webauthn_enabled = db.Column(db.Boolean, default=False)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        """Set user password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password is correct."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Check if user is an administrator."""
        return self.role == Role.ADMIN.value
    
    def generate_email_token(self):
        """Generate email verification token."""
        self.email_verification_token = str(uuid.uuid4())
        return self.email_verification_token
    
    def generate_password_reset_token(self):
        """Generate password reset token."""
        self.password_reset_token = str(uuid.uuid4())
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=2)
        return self.password_reset_token
    
    def __repr__(self):
        return f'<User {self.username}>'

class LoginSession(db.Model):
    """Model to track user login sessions."""
    
    __tablename__ = "login_sessions"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.String(128), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    device_info = db.Column(db.String(128), nullable=True)
    location = db.Column(db.String(128), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('login_sessions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<LoginSession {self.id}>'

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    return User.query.get(user_id)
