"""
Sync history model for tracking synchronization operations.

This module defines the SyncHistory class which tracks the history
of synchronization operations between credit cards and Monzo pots.
"""

import json
from datetime import datetime
from app.extensions import db
from app.utils.json_utils import dumps, loads

class SyncHistory(db.Model):
    """Model for tracking synchronization history.
    
    Attributes:
        id: Primary key
        timestamp: When the sync operation occurred
        status: Status of the sync operation
        data_json: JSON data about the sync operation
        user_id: User ID associated with the sync (optional)
    """
    
    __tablename__ = "sync_history"
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # completed, partial, failed, etc.
    data_json = db.Column(db.Text, nullable=True)  # JSON serialized data
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    def __init__(self, timestamp=None, status=None, data=None, user_id=None):
        """Initialize a sync history record.
        
        Args:
            timestamp: When the sync occurred (default: now)
            status: Status of the sync operation
            data: Data about the sync operation (will be JSON serialized)
            user_id: User ID associated with the sync
        """
        self.timestamp = timestamp or datetime.utcnow()
        self.status = status
        
        # Serialize data to JSON if provided
        if data is not None:
            self.data_json = dumps(data)
            
        self.user_id = user_id
    
    @property
    def data(self):
        """Get the deserialized data.
        
        Returns:
            dict: Deserialized data or empty dict if none/invalid
        """
        if not self.data_json:
            return {}
            
        try:
            return loads(self.data_json)
        except (json.JSONDecodeError, ValueError):
            return {}
    
    @data.setter
    def data(self, value):
        """Set the data, serializing to JSON.
        
        Args:
            value: Data to serialize
        """
        if value is None:
            self.data_json = None
        else:
            self.data_json = dumps(value)
    
    def __repr__(self):
        """String representation of the sync history record."""
        return f"<SyncHistory {self.id} status={self.status}>"
    
    def to_dict(self):
        """Convert sync history to dictionary.
        
        Returns:
            dict: Dictionary representation
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status,
            'data': self.data,
            'user_id': self.user_id
        }
