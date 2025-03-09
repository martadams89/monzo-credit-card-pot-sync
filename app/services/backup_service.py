"""Service for handling database backups."""

import os
import logging
import shutil
import time
import datetime
import subprocess
from pathlib import Path
import re
from sqlalchemy import create_engine, text
from flask import current_app
from flask_login import current_user
from app.models.backup import Backup

log = logging.getLogger("backup_service")

class BackupService:
    """Service for creating and managing database backups."""
    
    def __init__(self, setting_repository=None, backup_repository=None, db_session=None):
        """Initialize the backup service.
        
        Args:
            setting_repository: Repository for settings
            backup_repository: Repository for backup records
            db_session: SQLAlchemy database session (optional)
        """
        self.setting_repository = setting_repository
        self.backup_repository = backup_repository
        self.db = db_session
        
    def get_backup_dir(self):
        """Get the backup directory path."""
        backup_dir = self.setting_repository.get('backup_directory', 'backups')
        
        # If not absolute, make it relative to app root
        if not os.path.isabs(backup_dir):
            backup_dir = os.path.join(current_app.root_path, '..', backup_dir)
            
        # Ensure directory exists
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    def get_db_url(self):
        """Get database URL from app config."""
        return current_app.config.get('SQLALCHEMY_DATABASE_URI')
    
    def create_backup(self, reason="scheduled"):
        """Create a database backup.
        
        Args:
            reason: The reason for the backup (e.g., "scheduled", "migration", "manual")
            
        Returns:
            dict: Backup result with success status and file path or error message
        """
        try:
            db_url = self.get_db_url()
            if not db_url:
                return {"success": False, "error": "Database URL not configured"}
                
            backup_path = self._create_backup_file(db_url, reason)
            
            if backup_path:
                # Record in database if repository is available
                if self.backup_repository:
                    filename = os.path.basename(backup_path)
                    size = os.path.getsize(backup_path)
                    
                    # Get current user ID if available
                    user_id = getattr(current_user, 'id', None) if reason == "manual" else None
                    
                    backup_record = Backup(
                        filename=filename,
                        path=backup_path,
                        size=size,
                        reason=reason,
                        created_by_id=user_id
                    )
                    self.backup_repository.save(backup_record)
                
                self._cleanup_old_backups()
                log.info(f"Backup created successfully: {backup_path}")
                return {"success": True, "file": backup_path}
            else:
                log.error("Failed to create backup")
                return {"success": False, "error": "Backup creation failed"}
                
        except Exception as e:
            log.error(f"Backup error: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _create_backup_file(self, db_url, reason):
        """Create a backup file for the given database URL.
        
        Returns:
            str: Path to the backup file or None if failed
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.get_backup_dir()
        
        # Sanitize reason for use in filename
        reason_safe = re.sub(r'[^a-zA-Z0-9_]', '_', reason)
        
        if db_url.startswith('sqlite:///'):
            return self._backup_sqlite(db_url, backup_dir, timestamp, reason_safe)
        elif db_url.startswith(('mysql://', 'mysql+pymysql://')):
            return self._backup_mysql(db_url, backup_dir, timestamp, reason_safe)
        elif db_url.startswith('postgresql://'):
            return self._backup_postgres(db_url, backup_dir, timestamp, reason_safe)
        else:
            log.error(f"Unsupported database type: {db_url.split(':')[0]}")
            return None
    
    def _backup_sqlite(self, db_url, backup_dir, timestamp, reason):
        """Backup a SQLite database."""
        # Extract path from sqlite:///path format
        db_path = db_url.replace('sqlite:///', '')
        
        if not os.path.isabs(db_path):
            # Relative path - make it absolute relative to app root
            db_path = os.path.join(current_app.root_path, db_path)
            
        if not os.path.exists(db_path):
            log.error(f"SQLite database not found at {db_path}")
            return None
            
        backup_filename = f"backup_{timestamp}_{reason}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Create a copy of the database file
        shutil.copy2(db_path, backup_path)
        return backup_path
    
    def _backup_mysql(self, db_url, backup_dir, timestamp, reason):
        """Backup a MySQL database using mysqldump."""
        # Parse URL to extract connection info
        from urllib.parse import urlparse
        parsed = urlparse(db_url.replace('mysql+pymysql://', 'mysql://'))
        
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 3306
        database = parsed.path.strip('/')
        
        backup_filename = f"backup_{timestamp}_{reason}_{database}.sql"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Create mysqldump command
        cmd = [
            'mysqldump',
            f'--host={hostname}',
            f'--port={port}',
            f'--user={username}',
            f'--password={password}' if password else '',
            '--single-transaction',
            '--routines',
            '--triggers',
            '--databases', database,
            '-r', backup_path
        ]
        
        # Execute mysqldump
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            log.error(f"mysqldump failed: {process.stderr}")
            return None
            
        return backup_path
    
    def _backup_postgres(self, db_url, backup_dir, timestamp, reason):
        """Backup a PostgreSQL database using pg_dump."""
        # Parse URL to extract connection info
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.strip('/')
        
        backup_filename = f"backup_{timestamp}_{reason}_{database}.sql"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Set PGPASSWORD environment variable for password
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
        
        # Create pg_dump command
        cmd = [
            'pg_dump',
            f'--host={hostname}',
            f'--port={port}',
            f'--username={username}',
            '--format=plain',
            '--no-owner',
            '--no-acl',
            '-f', backup_path,
            database
        ]
        
        # Execute pg_dump
        process = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if process.returncode != 0:
            log.error(f"pg_dump failed: {process.stderr}")
            return None
            
        return backup_path
    
    def _cleanup_old_backups(self):
        """Delete backups beyond the retention period."""
        try:
            retention_days = int(self.setting_repository.get('backup_retention_days', '7'))
            if retention_days <= 0:
                # Retention disabled, keep all backups
                return
                
            backup_dir = self.get_backup_dir()
            now = time.time()
            max_age = retention_days * 86400  # days to seconds
            
            for file in os.listdir(backup_dir):
                if file.startswith('backup_'):
                    file_path = os.path.join(backup_dir, file)
                    file_age = now - os.path.getmtime(file_path)
                    
                    if file_age > max_age:
                        os.remove(file_path)
                        log.info(f"Deleted old backup: {file}")
                        
        except Exception as e:
            log.error(f"Error cleaning up old backups: {str(e)}")
            
    def list_backups(self):
        """List all available backups.
        
        Returns:
            list: List of backup info dictionaries
        """
        try:
            # If backup repository is available, use it
            if self.backup_repository:
                backup_records = self.backup_repository.get_all()
                backups = []
                
                for record in backup_records:
                    # Check if file still exists
                    if os.path.exists(record.path):
                        backups.append({
                            'id': record.id,
                            'filename': record.filename,
                            'path': record.path,
                            'size': record.size,
                            'created_at': record.created_at,
                            'reason': record.reason,
                            'created_by_id': record.created_by_id,
                            'restored_at': record.restored_at
                        })
                
                return backups
            
            # Fall back to directory scanning if no repository
            backups = []
            backup_dir = self.get_backup_dir()
            
            # Get all backup files
            for file in os.listdir(backup_dir):
                if file.startswith('backup_'):
                    file_path = os.path.join(backup_dir, file)
                    file_stat = os.stat(file_path)
                    
                    # Extract timestamp from filename
                    match = re.search(r'backup_(\d{8}_\d{6})_(.+?)[\._]', file)
                    if match:
                        timestamp_str = match.group(1)
                        reason = match.group(2)
                        
                        # Convert timestamp to datetime
                        timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        backups.append({
                            'filename': file,
                            'path': file_path,
                            'size': file_stat.st_size,
                            'created_at': timestamp,
                            'reason': reason
                        })
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return backups
            
        except Exception as e:
            log.error(f"Error listing backups: {str(e)}")
            return []
    
    def restore_backup(self, backup_path):
        """Restore database from a backup file.
        
        Args:
            backup_path: Path to the backup file
            
        Returns:
            dict: Restore result with success status and message
        """
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "error": f"Backup file not found: {backup_path}"}
                
            # Create a pre-restore backup
            pre_restore = self.create_backup(reason="pre_restore")
            if not pre_restore["success"]:
                log.warning(f"Failed to create pre-restore backup: {pre_restore.get('error')}")
                
            db_url = self.get_db_url()
            
            restoration_result = None
            if db_url.startswith('sqlite:///'):
                restoration_result = self._restore_sqlite(backup_path, db_url)
            elif db_url.startswith(('mysql://', 'mysql+pymysql://')):
                restoration_result = self._restore_mysql(backup_path, db_url)
            elif db_url.startswith('postgresql://'):
                restoration_result = self._restore_postgres(backup_path, db_url)
            else:
                return {"success": False, "error": f"Unsupported database type: {db_url.split(':')[0]}"}
                
            # Mark as restored in backup history if successful
            if restoration_result and restoration_result.get("success") and self.backup_repository:
                filename = os.path.basename(backup_path)
                self.backup_repository.mark_as_restored(filename)
            
            return restoration_result
                
        except Exception as e:
            log.error(f"Restore error: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _restore_sqlite(self, backup_path, db_url):
        """Restore a SQLite database."""
        # Extract path from sqlite:///path format
        db_path = db_url.replace('sqlite:///', '')
        
        if not os.path.isabs(db_path):
            # Relative path - make it absolute relative to app root
            db_path = os.path.join(current_app.root_path, db_path)
            
        # Copy backup to replace current db
        shutil.copy2(backup_path, db_path)
        return {"success": True, "message": "Database restored successfully"}
    
    def _restore_mysql(self, backup_path, db_url):
        """Restore a MySQL database."""
        from urllib.parse import urlparse
        parsed = urlparse(db_url.replace('mysql+pymysql://', 'mysql://'))
        
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 3306
        database = parsed.path.strip('/')
        
        # MySQL restore command
        cmd = [
            'mysql',
            f'--host={hostname}',
            f'--port={port}',
            f'--user={username}',
            f'--password={password}' if password else '',
            database
        ]
        
        with open(backup_path, 'r') as f:
            process = subprocess.run(cmd, stdin=f, capture_output=True, text=True)
            
        if process.returncode != 0:
            log.error(f"MySQL restore failed: {process.stderr}")
            return {"success": False, "error": process.stderr}
            
        return {"success": True, "message": "Database restored successfully"}
    
    def _restore_postgres(self, backup_path, db_url):
        """Restore a PostgreSQL database."""
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.strip('/')
        
        # Set PGPASSWORD environment variable for password
        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password
        
        # PostgreSQL restore command
        cmd = [
            'psql',
            f'--host={hostname}',
            f'--port={port}',
            f'--username={username}',
            '-d', database,
            '-f', backup_path
        ]
        
        process = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if process.returncode != 0:
            log.error(f"PostgreSQL restore failed: {process.stderr}")
            return {"success": False, "error": process.stderr}
            
        return {"success": True, "message": "Database restored successfully"}
