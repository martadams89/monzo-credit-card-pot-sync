"""User model for authentication"""

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from app.extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    
    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100), nullable=True)
    email_verification_expiry = db.Column(db.DateTime, nullable=True)
    
    # Two-factor authentication fields
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.String(500), nullable=True)  # Stored as JSON string
    
    # Passkey support (WebAuthn)
    passkeys = db.Column(db.Text, default='[]')  # JSON array of registered passkeys
    
    # User preferences
    preferences = db.Column(db.Text, default='{}')  # JSON string
    
    # Registration and last login
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    
    def __init__(self, username, email, password=None, is_admin=False):
        self.username = username
        self.email = email
        if password:
            self.set_password(password)
        self.is_admin = is_admin
        self.passkeys = '[]'
        self.preferences = '{}'
    
    def set_password(self, password):
        """Set user password with hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check password against stored hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def requires_2fa(self):
        """Check if user requires 2FA"""
        return self.totp_enabled
    
    @property
    def has_passkeys(self):
        """Check if user has passkeys registered"""
        import json
        if not self.passkeys:
            return False
        return len(json.loads(self.passkeys)) > 0
        
    def __repr__(self):
        return f'<User {self.username}>'
