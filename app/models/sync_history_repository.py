"""
Repository for sync history database operations.

This module provides a repository pattern implementation for managing
sync history records in the database.
"""

import logging
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from app.models.sync_history import SyncHistory

log = logging.getLogger(__name__)

class SqlAlchemySyncHistoryRepository:
    """SQL Alchemy implementation of sync history repository."""
    
    def __init__(self, db_session):
        """Initialize repository with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def add_sync_record(self, timestamp=None, status=None, data=None, user_id=None):
        """Add a new sync record.
        
        Args:
            timestamp: When the sync occurred (default: now)
            status: Status of the sync operation
            data: Data about the sync operation
            user_id: User ID associated with the sync
            
        Returns:
            SyncHistory: Created record or None if failed
        """
        try:
            # Create sync history record
            record = SyncHistory(
                timestamp=timestamp or datetime.utcnow(),
                status=status,
                data=data,
                user_id=user_id
            )
            
            # Save to database
            self.db.session.add(record)
            self.db.session.commit()
            return record
            
        except SQLAlchemyError as e:
            log.error(f"Error adding sync record: {e}")
            self.db.session.rollback()
            return None
    
    def get_recent_syncs(self, limit=10):
        """Get most recent sync records.
        
        Args:
            limit: Maximum number of records to retrieve
            
        Returns:
            list: Recent sync records as dictionaries
        """
        try:
            records = SyncHistory.query.order_by(
                desc(SyncHistory.timestamp)
            ).limit(limit).all()
            
            return [record.to_dict() for record in records]
            
        except SQLAlchemyError as e:
            log.error(f"Error retrieving recent syncs: {e}")
            return []
    
    def get_syncs_in_range(self, start_date, end_date):
        """Get sync records within a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            list: Sync records in range as dictionaries
        """
        try:
            records = SyncHistory.query.filter(
                SyncHistory.timestamp >= start_date,
                SyncHistory.timestamp <= end_date
            ).order_by(desc(SyncHistory.timestamp)).all()
            
            return [record.to_dict() for record in records]
            
        except SQLAlchemyError as e:
            log.error(f"Error retrieving syncs in range: {e}")
            return []
    
    def get_user_syncs(self, user_id, limit=10):
        """Get sync records for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of records to retrieve
            
        Returns:
            list: User's sync records as dictionaries
        """
        try:
            records = SyncHistory.query.filter_by(
                user_id=user_id
            ).order_by(desc(SyncHistory.timestamp)).limit(limit).all()
            
            return [record.to_dict() for record in records]
            
        except SQLAlchemyError as e:
            log.error(f"Error retrieving user syncs: {e}")
            return []
    
    def clear_old_records(self, days_to_keep=30):
        """Remove old sync history records.
        
        Args:
            days_to_keep: Number of days of history to retain
            
        Returns:
            int: Number of records deleted
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete records older than cutoff
            count = SyncHistory.query.filter(
                SyncHistory.timestamp < cutoff_date
            ).delete()
            
            self.db.session.commit()
            return count
            
        except SQLAlchemyError as e:
            log.error(f"Error clearing old sync records: {e}")
            self.db.session.rollback()
            return 0
