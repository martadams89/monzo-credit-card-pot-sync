"""Model for tracking synchronization records."""

from app.extensions import db
from datetime import datetime

class SyncRecord(db.Model):
    """Model for tracking synchronization operations."""
    
    __tablename__ = 'sync_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, success, failed, partial
    details = db.Column(db.Text)
    
    user = db.relationship('User', back_populates='sync_records')
    
    def __repr__(self):
        """Return a string representation of the sync record."""
        return f'<SyncRecord {self.id} - {self.status}>'
