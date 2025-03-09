"""Repository for backup database operations."""

import logging
from sqlalchemy.exc import SQLAlchemyError
from app.models.backup import Backup

log = logging.getLogger("backup_repository")

class SqlAlchemyBackupRepository:
    """SQL Alchemy implementation of backup repository."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def save(self, backup):
        """Save a backup record."""
        try:
            self.db.session.add(backup)
            self.db.session.commit()
            return backup
        except SQLAlchemyError as e:
            log.error(f"Error saving backup record: {e}")
            self.db.session.rollback()
            return None
    
    def get_by_id(self, backup_id):
        """Get a backup by ID."""
        return Backup.query.get(backup_id)
    
    def get_by_filename(self, filename):
        """Get a backup by filename."""
        return Backup.query.filter_by(filename=filename).first()
    
    def get_all(self, limit=None):
        """Get all backups, optionally limited."""
        query = Backup.query.order_by(Backup.created_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def delete(self, backup_id):
        """Delete a backup record."""
        try:
            backup = Backup.query.get(backup_id)
            if backup:
                self.db.session.delete(backup)
                self.db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            log.error(f"Error deleting backup record: {e}")
            self.db.session.rollback()
            return False
    
    def mark_as_restored(self, filename):
        """Mark a backup as restored."""
        try:
            from datetime import datetime
            backup = Backup.query.filter_by(filename=filename).first()
            if backup:
                backup.restored_at = datetime.utcnow()
                self.db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            log.error(f"Error marking backup as restored: {e}")
            self.db.session.rollback()
            return False
    
    def get_latest(self):
        """Get the latest backup."""
        return Backup.query.order_by(Backup.created_at.desc()).first()
    
    def count(self):
        """Count total backups."""
        return Backup.query.count()
