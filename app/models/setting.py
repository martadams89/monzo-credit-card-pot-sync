"""Model for application settings."""

from datetime import datetime
from app.extensions import db

class Setting(db.Model):
    """Model for application settings."""
    
    __tablename__ = 'settings'
    
    key = db.Column(db.String(255), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    
    # Remove timestamp columns for now as they don't exist in the database yet
    # created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        """Return string representation."""
        return f'<Setting {self.key}>'
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value directly.
        
        Args:
            key: Setting key
            default: Default value if setting is not found
            
        Returns:
            The setting value or default
        """
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default