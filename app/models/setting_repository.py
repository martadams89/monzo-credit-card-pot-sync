"""Repository for managing settings in the database."""

import logging
from app.models.setting import Setting
from app.extensions import db

logger = logging.getLogger(__name__)

class SqlAlchemySettingRepository:
    """Repository for managing settings using SQLAlchemy."""
    
    def __init__(self, db_instance=None):
        """Initialize the repository."""
        self.db = db_instance or db
        
    def get(self, key, default=None):
        """Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found
            
        Returns:
            The setting value or default
        """
        setting = Setting.query.filter_by(key=key).first()
        
        if not setting:
            return default
            
        return setting.value
    
    def save(self, setting):
        """Save a setting.
        
        Args:
            setting: Setting instance to save
            
        Returns:
            Setting instance
        """
        try:
            # Check if setting already exists
            existing = Setting.query.filter_by(key=setting.key).first()
            
            if existing:
                # Update existing setting
                existing.value = setting.value
                self.db.session.commit()
                return existing
            else:
                # Add new setting
                self.db.session.add(setting)
                self.db.session.commit()
                return setting
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving setting {setting.key}: {str(e)}")
            raise
    
    def save_setting(self, key, value):
        """Save a setting by key and value.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            Setting instance
        """
        # Check if setting already exists
        setting = Setting.query.filter_by(key=key).first()
        
        if setting:
            # Update existing setting
            setting.value = value
        else:
            # Create new setting
            setting = Setting(key=key, value=value)
            self.db.session.add(setting)
            
        try:
            self.db.session.commit()
            return setting
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving setting {key}: {str(e)}")
            raise
    
    def delete(self, key):
        """Delete a setting by key.
        
        Args:
            key: Setting key
            
        Returns:
            True if deleted, False if not found
        """
        setting = Setting.query.filter_by(key=key).first()
        
        if not setting:
            return False
            
        try:
            self.db.session.delete(setting)
            self.db.session.commit()
            return True
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error deleting setting {key}: {str(e)}")
            raise
    
    def get_by_prefix(self, prefix):
        """Get all settings with a given key prefix.
        
        Args:
            prefix: Key prefix to filter by
            
        Returns:
            List of Setting instances
        """
        return Setting.query.filter(Setting.key.startswith(prefix)).all()
    
    def get_all(self):
        """Get all settings.
        
        Returns:
            List of Setting instances
        """
        return Setting.query.all()
