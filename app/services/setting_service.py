"""Service for managing application settings."""

import json
import logging
from datetime import datetime
from app.models.setting import Setting
from app.extensions import db

logger = logging.getLogger(__name__)

class SettingService:
    """Service for managing application settings."""
    
    def __init__(self):
        """Initialize the service."""
        pass
    
    def get_setting(self, key, default=None, user_id=None):
        """Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found
            user_id: User ID for user-specific settings
            
        Returns:
            The setting value or default
        """
        setting_key = f"user:{user_id}:{key}" if user_id else key
        
        try:
            # Try to get from database
            setting = Setting.query.filter_by(key=setting_key).first()
            
            if not setting:
                return default
                
            return setting.value
        except Exception as e:
            logger.error(f"Error retrieving setting {setting_key}: {str(e)}")
            return default
    
    def save_setting(self, key, value, user_id=None):
        """Save a setting value.
        
        Args:
            key: Setting key
            value: Setting value
            user_id: User ID for user-specific settings
            
        Returns:
            True if successful, False otherwise
        """
        setting_key = f"user:{user_id}:{key}" if user_id else key
        
        # Try to get existing setting
        setting = Setting.query.filter_by(key=setting_key).first()
        
        if setting:
            # Update existing setting
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            # Create new setting
            setting = Setting(key=setting_key, value=value)
            db.session.add(setting)
            
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving setting {setting_key}: {str(e)}")
            return False
    
    def delete_setting(self, key, user_id=None):
        """Delete a setting.
        
        Args:
            key: Setting key
            user_id: User ID for user-specific settings
            
        Returns:
            True if successful, False otherwise
        """
        setting_key = f"user:{user_id}:{key}" if user_id else key
        
        # Try to get existing setting
        setting = Setting.query.filter_by(key=setting_key).first()
        
        if not setting:
            return True  # Already doesn't exist
            
        try:
            db.session.delete(setting)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting setting {setting_key}: {str(e)}")
            return False
    
    def get_user_settings(self, user_id, category=None):
        """Get all settings for a user.
        
        Args:
            user_id: User ID
            category: Optional category prefix
            
        Returns:
            Dict of setting key/value pairs
        """
        prefix = f"user:{user_id}:"
        if category:
            prefix += f"{category}:"
            
        settings = Setting.query.filter(
            Setting.key.startswith(prefix)
        ).all()
        
        result = {}
        for setting in settings:
            # Strip the prefix
            key = setting.key[len(prefix):]
            result[key] = setting.value
            
        return result
    
    def get_boolean(self, key, default=False, user_id=None):
        """Get a boolean setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found
            user_id: User ID for user-specific settings
            
        Returns:
            Boolean value
        """
        value = self.get_setting(key, default, user_id)
        
        if isinstance(value, bool):
            return value
            
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
            
        return bool(value)
    
    def get_json(self, key, default=None, user_id=None):
        """Get a JSON setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found or invalid
            user_id: User ID for user-specific settings
            
        Returns:
            Parsed JSON value or default
        """
        value = self.get_setting(key, None, user_id)
        
        if not value:
            return default
            
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in setting {key}")
            return default
    
    def save_json(self, key, value, user_id=None):
        """Save a JSON setting value.
        
        Args:
            key: Setting key
            value: Value to save as JSON
            user_id: User ID for user-specific settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            json_value = json.dumps(value)
            return self.save_setting(key, json_value, user_id)
        except Exception as e:
            logger.error(f"Error saving JSON setting {key}: {str(e)}")
            return False
    
    def get_int(self, key, default=0, user_id=None):
        """Get an integer setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found or invalid
            user_id: User ID for user-specific settings
            
        Returns:
            Integer value
        """
        value = self.get_setting(key, default, user_id)
        
        if isinstance(value, int):
            return value
            
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key, default=0.0, user_id=None):
        """Get a float setting value.
        
        Args:
            key: Setting key
            default: Default value if setting is not found or invalid
            user_id: User ID for user-specific settings
            
        Returns:
            Float value
        """
        value = self.get_setting(key, default, user_id)
        
        if isinstance(value, float):
            return value
            
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
