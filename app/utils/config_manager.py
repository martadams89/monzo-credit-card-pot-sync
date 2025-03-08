"""Configuration management system"""

import os
import json
import logging
from app.models.setting_repository import SqlAlchemySettingRepository
from app.domain.settings import Setting

log = logging.getLogger(__name__)

class ConfigManager:
    """Manage application configuration from multiple sources"""
    
    def __init__(self, db=None):
        self.env_configs = {}
        self.db_configs = {}
        self.file_configs = {}
        self.db_repository = SqlAlchemySettingRepository(db) if db else None
        
    def load_from_env(self, prefix="MCCS_"):
        """Load configuration from environment variables"""
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self.env_configs[config_key] = value
                
        log.info(f"Loaded {len(self.env_configs)} configuration values from environment")
        
    def load_from_db(self):
        """Load configuration from database"""
        if not self.db_repository:
            log.warning("No database repository available, skipping DB config load")
            return
            
        settings = self.db_repository.get_all()
        for setting in settings:
            self.db_configs[setting.key] = setting.value
            
        log.info(f"Loaded {len(self.db_configs)} configuration values from database")
        
    def load_from_file(self, filepath):
        """Load configuration from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                configs = json.load(f)
                self.file_configs.update(configs)
                
            log.info(f"Loaded {len(configs)} configuration values from {filepath}")
        except Exception as e:
            log.error(f"Failed to load configuration from {filepath}: {e}")
            
    def get(self, key, default=None):
        """Get a configuration value with priority: env > db > file > default"""
        # Check environment configs first
        if key in self.env_configs:
            return self.env_configs[key]
            
        # Then database configs
        if key in self.db_configs:
            return self.db_configs[key]
            
        # Then file configs
        if key in self.file_configs:
            return self.file_configs[key]
            
        # Finally return default
        return default
        
    def set(self, key, value, persist_to_db=True):
        """Set a configuration value"""
        self.db_configs[key] = value
        
        if persist_to_db and self.db_repository:
            self.db_repository.save(Setting(key, value))
