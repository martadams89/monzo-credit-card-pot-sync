"""
Cooldown model for tracking deposit cooldown periods.

This module defines the Cooldown class which tracks cooldown periods after
account transfers to prevent excessive movements of funds.
"""

from datetime import datetime
from app.extensions import db

class Cooldown(db.Model):
    """Model for tracking cooldown periods for accounts.
    
    Attributes:
        id: Primary key
        account_id: External account identifier
        user_id: User ID who owns the account
        started_at: When the cooldown period started
        expires_at: When the cooldown period ends
        initial_balance: Balance at start of cooldown
    """
    
    __tablename__ = "cooldowns"
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.String(255), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    initial_balance = db.Column(db.Integer, nullable=True)
    
    # Relationship with User
    user = db.relationship('User', back_populates='cooldowns')
    
    def __init__(self, account_id, user_id, expires_at, initial_balance=None):
        """Initialize a cooldown record.
        
        Args:
            account_id: External account identifier
            user_id: User ID who owns the account
            expires_at: When the cooldown period ends
            initial_balance: Balance at start of cooldown (optional)
        """
        self.account_id = account_id
        self.user_id = user_id
        self.expires_at = expires_at
        self.initial_balance = initial_balance
        
    def is_expired(self):
        """Check if cooldown has expired.
        
        Returns:
            bool: True if cooldown has expired, False otherwise
        """
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        """String representation of the cooldown."""
        return f"<Cooldown {self.account_id} expires_at={self.expires_at}>"
