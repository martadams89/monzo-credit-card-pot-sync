"""Backup history model for tracking database backups."""

from datetime import datetime
from app.extensions import db

class Backup(db.Model):
    """Model for tracking database backup history."""
    
    __tablename__ = "backups"
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    size = db.Column(db.Integer, nullable=False)  # Size in bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    created_by_id = db.Column(db.Integer, nullable=True)  # User ID if manually created
    restored_at = db.Column(db.DateTime, nullable=True)  # When/if this backup was restored
    
    def __init__(self, filename, path, size, reason, created_by_id=None):
        """Initialize a backup record."""
        self.filename = filename
        self.path = path
        self.size = size
        self.reason = reason
        self.created_by_id = created_by_id
    
    def __repr__(self):
        """String representation of the backup."""
        return f"<Backup {self.filename}>"
    
    def to_dict(self):
        """Convert backup to dictionary."""
        return {
            'id': self.id,
            'filename': self.filename,
            'path': self.path,
            'size': self.size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reason': self.reason,
            'created_by_id': self.created_by_id,
            'restored_at': self.restored_at.isoformat() if self.restored_at else None
        }
