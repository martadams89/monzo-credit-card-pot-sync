import os
import sys
import shutil
import sqlite3
import datetime
import logging
import gzip
import json
from pathlib import Path
from flask import current_app

log = logging.getLogger(__name__)

def create_backup():
    """
    Create a backup of the SQLite database.
    
    Returns:
        dict: Result information including success status, filename, and message
    """
    try:
        # Get database path from config
        db_url = current_app.config['SQLALCHEMY_DATABASE_URI']
        if not db_url.startswith('sqlite:///'):
            return {
                'success': False,
                'message': 'Only SQLite databases are supported for backup'
            }
        
        # Extract database path
        db_path = db_url.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            # Convert relative path to absolute
            db_path = os.path.join(current_app.instance_path, db_path)
        
        # Create backup directory if it doesn't exist
        backup_dir = os.path.join(current_app.instance_path, current_app.config['BACKUP_DIRECTORY'])
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.sqlite.gz"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy the database to backup
        with sqlite3.connect(db_path) as conn:
            # Create a backup with the sqlite3 .backup command (transactions secure)
            with open(backup_path + '.temp', 'wb') as f:
                for data in conn.iterdump():
                    f.write(f"{data}\n".encode('utf-8'))
        
        # Compress the backup
        with open(backup_path + '.temp', 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove temporary file
        os.remove(backup_path + '.temp')
        
        # Manage backup rotation (keep only the last N backups)
        rotate_backups(backup_dir, current_app.config['BACKUP_COUNT'])
        
        log.info(f"Database backup created successfully: {backup_filename}")
        return {
            'success': True,
            'filename': backup_filename,
            'path': backup_path,
            'message': f"Backup created successfully: {backup_filename}"
        }
        
    except Exception as e:
        log.error(f"Error creating backup: {str(e)}")
        return {
            'success': False,
            'message': f"Error creating backup: {str(e)}"
        }

def restore_backup(filename):
    """
    Restore database from a backup file.
    
    Args:
        filename: Name of the backup file
    
    Returns:
        dict: Result information including success status and message
    """
    try:
        # Get database path from config
        db_url = current_app.config['SQLALCHEMY_DATABASE_URI']
        if not db_url.startswith('sqlite:///'):
            return {
                'success': False,
                'message': 'Only SQLite databases are supported for restore'
            }
        
        # Extract database path
        db_path = db_url.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            # Convert relative path to absolute
            db_path = os.path.join(current_app.instance_path, db_path)
        
        # Get backup directory
        backup_dir = os.path.join(current_app.instance_path, current_app.config['BACKUP_DIRECTORY'])
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            return {
                'success': False,
                'message': f"Backup file not found: {filename}"
            }
        
        # Create a backup of the current database before restoring
        pre_restore_backup = create_backup()
        if not pre_restore_backup['success']:
            return {
                'success': False,
                'message': f"Failed to create safety backup before restore: {pre_restore_backup['message']}"
            }
            
        # Decompress backup file to temporary location
        temp_path = os.path.join(backup_dir, 'temp_restore.sql')
        with gzip.open(backup_path, 'rb') as f_in:
            with open(temp_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Close any connections to the database
        from app.extensions import db
        db.session.close_all()
        
        # Remove the current database
        if os.path.exists(db_path):
            os.rename(db_path, f"{db_path}.bak")
        
        # Create a new database from the backup
        conn = sqlite3.connect(db_path)
        with open(temp_path, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        
        # Clean up
        os.remove(temp_path)
        
        log.info(f"Database restored successfully from backup: {filename}")
        return {
            'success': True,
            'message': f"Database restored successfully from backup: {filename}"
        }
        
    except Exception as e:
        log.error(f"Error restoring backup: {str(e)}")
        
        # Try to restore the original database if there was an error
        try:
            if os.path.exists(f"{db_path}.bak"):
                os.rename(f"{db_path}.bak", db_path)
        except:
            pass
            
        return {
            'success': False,
            'message': f"Error restoring backup: {str(e)}"
        }

def get_backups():
    """
    Get list of available backups.
    
    Returns:
        list: List of backup info dictionaries
    """
    try:
        # Get backup directory
        backup_dir = os.path.join(current_app.instance_path, current_app.config['BACKUP_DIRECTORY'])
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Get list of backup files
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('backup_') and filename.endswith('.sqlite.gz'):
                file_path = os.path.join(backup_dir, filename)
                file_stats = os.stat(file_path)
                
                # Parse timestamp from filename
                timestamp_str = filename.replace('backup_', '').replace('.sqlite.gz', '')
                try:
                    timestamp = datetime.datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                except:
                    timestamp = datetime.datetime.fromtimestamp(file_stats.st_ctime)
                
                backups.append({
                    'filename': filename,
                    'size': file_stats.st_size,
                    'size_formatted': format_size(file_stats.st_size),
                    'created_at': timestamp,
                    'created_at_formatted': timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # Sort backups by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
        
    except Exception as e:
        log.error(f"Error getting backups: {str(e)}")
        return []

def delete_backup(filename):
    """
    Delete a backup file.
    
    Args:
        filename: Name of the backup file
    
    Returns:
        dict: Result information including success status and message
    """
    try:
        # Get backup directory
        backup_dir = os.path.join(current_app.instance_path, current_app.config['BACKUP_DIRECTORY'])
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            return {
                'success': False,
                'message': f"Backup file not found: {filename}"
            }
        
        # Delete the backup file
        os.remove(backup_path)
        
        log.info(f"Backup deleted: {filename}")
        return {
            'success': True,
            'message': f"Backup deleted: {filename}"
        }
        
    except Exception as e:
        log.error(f"Error deleting backup: {str(e)}")
        return {
            'success': False,
            'message': f"Error deleting backup: {str(e)}"
        }

def rotate_backups(backup_dir, keep_count):
    """
    Delete old backups keeping only the specified number of most recent backups.
    
    Args:
        backup_dir: Directory where backups are stored
        keep_count: Number of backups to keep
    """
    try:
        # Get list of backup files
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('backup_') and filename.endswith('.sqlite.gz'):
                file_path = os.path.join(backup_dir, filename)
                file_stats = os.stat(file_path)
                backup_files.append((filename, file_stats.st_mtime))
        
        # Sort by modification time (oldest first)
        backup_files.sort(key=lambda x: x[1])
        
        # Remove old backups, keeping only keep_count most recent
        if len(backup_files) > keep_count:
            for filename, _ in backup_files[:-keep_count]:
                os.remove(os.path.join(backup_dir, filename))
                log.info(f"Removed old backup: {filename}")
                
    except Exception as e:
        log.error(f"Error rotating backups: {str(e)}")

def format_size(size_bytes):
    """
    Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        str: Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def export_data(user_id):
    """
    Export user data in JSON format.
    
    Args:
        user_id: ID of the user whose data to export
    
    Returns:
        dict: Result information including success status, data, and message
    """
    try:
        from app.models.user import User
        from app.models.monzo import MonzoAccount, MonzoPot, SyncRule, SyncHistory
        
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User not found'
            }
        
        # Build export data structure
        export_data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            },
            'accounts': [],
            'rules': [],
            'history': []
        }
        
        # Add accounts and pots
        accounts = MonzoAccount.query.filter_by(user_id=user_id).all()
        for account in accounts:
            account_data = {
                'id': account.id,
                'name': account.name,
                'type': account.type,
                'account_id': account.account_id,
                'balance': account.balance,
                'currency': account.currency,
                'is_active': account.is_active,
                'sync_enabled': account.sync_enabled,
                'created_at': account.created_at.isoformat(),
                'pots': []
            }
            
            # Add pots for this account
            pots = MonzoPot.query.filter_by(account_id=account.id).all()
            for pot in pots:
                account_data['pots'].append({
                    'id': pot.id,
                    'name': pot.name,
                    'pot_id': pot.pot_id,
                    'balance': pot.balance,
                    'currency': pot.currency,
                    'is_locked': pot.is_locked,
                    'created_at': pot.created_at.isoformat()
                })
                
            export_data['accounts'].append(account_data)
        
        # Add sync rules
        rules = SyncRule.query.filter_by(user_id=user_id).all()
        for rule in rules:
            rule_data = {
                'id': rule.id,
                'name': rule.name,
                'source_account_id': rule.source_account_id,
                'target_pot_id': rule.target_pot_id,
                'trigger_type': rule.trigger_type,
                'action_type': rule.action_type,
                'action_amount': rule.action_amount,
                'action_percentage': rule.action_percentage,
                'is_active': rule.is_active,
                'created_at': rule.created_at.isoformat(),
                'updated_at': rule.updated_at.isoformat()
            }
            export_data['rules'].append(rule_data)
        
        # Add sync history
        history = SyncHistory.query.filter_by(user_id=user_id).order_by(SyncHistory.created_at.desc()).limit(100).all()
        for entry in history:
            history_data = {
                'id': entry.id,
                'rule_id': entry.rule_id,
                'amount': entry.amount,
                'status': entry.status,
                'details': entry.details,
                'created_at': entry.created_at.isoformat()
            }
            export_data['history'].append(history_data)
        
        return {
            'success': True,
            'data': export_data,
            'message': 'Data exported successfully'
        }
        
    except Exception as e:
        log.error(f"Error exporting data: {str(e)}")
        return {
            'success': False,
            'message': f"Error exporting data: {str(e)}"
        }
