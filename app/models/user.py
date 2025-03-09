"""
User model for the application.

This module defines the User class which represents application users,
including authentication, roles, and relationships with other models.
"""

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login

class User(UserMixin, db.Model):
    """User model for authentication and access control.
    
    Attributes:
        id: Primary key
        username: User's unique username
        email: User's email address
        password_hash: Hashed password for authentication
        is_admin: Whether the user has administrator privileges
        is_active: Whether the account is active
        email_verified: Whether the email has been verified
        created_at: When the user account was created
        updated_at: When the user account was last updated
        last_login: When the user last logged in
    """
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=True)  # Default to True to simplify onboarding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    accounts = db.relationship('Account', back_populates='user', cascade='all, delete-orphan')
    cooldowns = db.relationship('Cooldown', back_populates='user', cascade='all, delete-orphan')
    sync_records = db.relationship('SyncRecord', back_populates='user', lazy='dynamic')
    
    def __repr__(self):
        """String representation of the user."""
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Set the user's password hash.
        
        Args:
            password: Plain text password to hash
        """
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check if the password is correct.
        
        Args:
            password: Plain text password to check
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        """Return the user id as a string.
        
        Required by Flask-Login.
        
        Returns:
            str: User ID
        """
        return str(self.id)
    
    def to_dict(self):
        """Convert the user to a dictionary.
        
        Returns:
            dict: User data as a dictionary
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def add_passkey(self, passkey_id):
        """Add a new passkey for this user."""
        from app.models.passkey import Passkey
        passkey = Passkey(user_id=self.id, credential_id=passkey_id)
        db.session.add(passkey)
        return passkey
        
    @property
    def has_passkeys(self):
        """Check if the user has any passkeys."""
        from app.models.passkey import Passkey
        return Passkey.query.filter_by(user_id=self.id).count() > 0

    def update_last_login(self):
        """Update the user's last login time."""
        self.last_login = datetime.utcnow()
        db.session.commit()

@login.user_loader
def load_user(id):
    """Load user for Flask-Login."""
    return User.query.get(int(id))
