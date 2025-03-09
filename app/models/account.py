"""Account model for the application."""

from datetime import datetime, timedelta
from app.extensions import db

class Account(db.Model):
    """Account model for storing bank and card account information."""
    
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.String(128), nullable=True)  # External account ID
    name = db.Column(db.String(64), nullable=True)  # Display name
    type = db.Column(db.String(20), nullable=False)  # monzo, credit_card
    provider = db.Column(db.String(20), nullable=True)  # truelayer, monzo, etc.
    access_token = db.Column(db.String(1024), nullable=True)
    refresh_token = db.Column(db.String(1024), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    balance = db.Column(db.Integer, nullable=True)  # Store balance in cents/pennies
    
    # Cooldown settings
    cooldown_until = db.Column(db.DateTime, nullable=True)
    cooldown_ref_card_balance = db.Column(db.Integer, nullable=True)
    cooldown_ref_pot_balance = db.Column(db.Integer, nullable=True)
    stable_pot_balance = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        """String representation of the account."""
        return f'<Account {self.id}: {self.display_name()}>'
    
    def display_name(self):
        """Get account display name."""
        if self.name:
            return self.name
        
        if self.type == 'monzo':
            return 'Monzo Account'
        elif self.type == 'credit_card':
            return 'Credit Card'
        else:
            return f'{self.type.capitalize()} Account'
    
    def is_in_cooldown(self):
        """Check if the account is in cooldown period."""
        if not self.cooldown_until:
            return False
        
        return datetime.utcnow() <= self.cooldown_until
    
    def set_cooldown(self, hours=3):
        """Set cooldown period for the account."""
        if hours > 0:
            self.cooldown_until = datetime.utcnow() + timedelta(hours=hours)
        else:
            self.cooldown_until = None
    
    def get_cooldown_expiry(self):
        """Get cooldown expiry time or None if not in cooldown."""
        return self.cooldown_until if self.is_in_cooldown() else None
    
    def is_token_expired(self):
        """Check if access token is expired."""
        if not self.token_expiry:
            return True
        
        return datetime.utcnow() >= self.token_expiry
    
    def to_dict(self):
        """Convert account to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'name': self.name,
            'type': self.type,
            'provider': self.provider,
            'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'balance': self.balance,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
            'in_cooldown': self.is_in_cooldown()
        }