"""Utility for managing database migrations more efficiently."""

import logging
import os
import subprocess
import datetime
from flask import current_app

logger = logging.getLogger(__name__)

class MigrationsManager:
    """Manager for database migrations."""
    
    @staticmethod
    def create_migration(name, message=None, autogenerate=True):
        """Create a new migration file.
        
        Args:
            name: Migration name
            message: Migration message
            autogenerate: Whether to autogenerate the migration
            
        Returns:
            Path to created migration file or None if failed
        """
        try:
            import alembic.config
            from flask_migrate import migrate as flask_migrate
            
            # Generate migration with Flask-Migrate
            revision = flask_migrate(
                directory=current_app.extensions['migrate'].directory,
                message=message or name,
                autogenerate=autogenerate
            )
            
            if not revision:
                logger.warning("No migration generated (no changes detected)")
                return None
                
            logger.info(f"Created migration revision: {revision}")
            return revision
        except Exception as e:
            logger.error(f"Error creating migration: {str(e)}")
            return None
    
    @staticmethod
    def apply_migrations(target=None):
        """Apply database migrations.
        
        Args:
            target: Target revision to migrate to (None for latest)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import flask_migrate
            
            # Apply migrations
            flask_migrate.upgrade(directory=None, revision=target)
            
            logger.info("Database migrations applied successfully")
            return True
        except Exception as e:
            logger.error(f"Error applying migrations: {str(e)}")
            return False
    
    @staticmethod
    def generate_fix_migrations():
        """Generate migrations to fix schema issues.
        
        This utility method detects common schema issues and generates migrations
        to fix them based on model definitions.
        
        Returns:
            True if migrations were generated, False otherwise
        """
        from app.extensions import db
        from sqlalchemy import inspect
        from app.models.setting import Setting
        from app.models.account import Account
        
        migrations_needed = []
        inspector = inspect(db.engine)
        
        # Check settings table for missing timestamp columns
        if 'settings' in inspector.get_table_names():
            settings_columns = [col['name'] for col in inspector.get_columns('settings')]
            if 'created_at' not in settings_columns or 'updated_at' not in settings_columns:
                migrations_needed.append({
                    'name': 'add_timestamp_to_settings',
                    'message': 'Add timestamp columns to settings table'
                })
                
        # Check accounts table for missing name column
        if 'accounts' in inspector.get_table_names():
            account_columns = [col['name'] for col in inspector.get_columns('accounts')]
            if 'name' not in account_columns:
                migrations_needed.append({
                    'name': 'add_name_to_accounts',
                    'message': 'Add name column to accounts table'
                })
        
        # Generate migrations
        for migration in migrations_needed:
            MigrationsManager.create_migration(
                migration['name'],
                migration['message'],
                autogenerate=False  # Don't autogenerate, we'll write them manually
            )
            
        return len(migrations_needed) > 0
