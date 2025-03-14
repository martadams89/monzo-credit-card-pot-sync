import uuid
from datetime import datetime
from app.extensions import db

class ApiKey(db.Model):
    """Model for API keys."""
    
    __tablename__ = "api_keys"
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user_account.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL means no expiration
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Explicitly define the relationship without a backref to avoid conflicts
    user = db.relationship('User', foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<ApiKey {self.id}: {self.name}>'
    
    @property
    def is_expired(self):
        """Check if the API key is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def update_last_used(self):
        """Update the last used timestamp."""
        self.last_used_at = datetime.utcnow()
