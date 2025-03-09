"""Repository for sync history records."""

import logging
import json
from datetime import datetime, timedelta
from app.models.sync_record import SyncRecord
from app.models.base_repository import BaseRepository
from app.extensions import db
from sqlalchemy import func

logger = logging.getLogger(__name__)

class SqlAlchemyHistoryRepository(BaseRepository):
    """Repository for sync history records using SQLAlchemy."""
    
    def __init__(self, db_instance=None):
        """Initialize the repository."""
        super().__init__(db_instance, SyncRecord)
    
    def save_sync_history(self, data, user_id=None):
        """Save a sync history record.
        
        Args:
            data: JSON serializable data to save
            user_id: User ID associated with the sync
            
        Returns:
            SyncRecord: The created sync record
        """
        if isinstance(data, dict):
            # Extract status from dictionary
            status = data.get('status', 'unknown')
            data_str = json.dumps(data)
        else:
            # Assume data is already JSON string
            data_str = data
            try:
                parsed = json.loads(data_str)
                status = parsed.get('status', 'unknown')
            except json.JSONDecodeError:
                status = 'unknown'
        
        # Create record
        record = SyncRecord(
            user_id=user_id,
            status=status,
            details=data_str,
            timestamp=datetime.utcnow()
        )
        
        try:
            self.db.session.add(record)
            self.db.session.commit()
            return record
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving sync history: {str(e)}")
            raise
    
    def get_recent_syncs_for_user(self, user_id, limit=5):
        """Get recent sync records for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of SyncRecord instances
        """
        return SyncRecord.query.filter_by(user_id=user_id).order_by(
            SyncRecord.timestamp.desc()
        ).limit(limit).all()
    
    def get_sync_stats_for_user(self, user_id, days=30):
        """Get sync statistics for a user over a period.
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            Dictionary with sync statistics
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Query for daily stats
        query = self.db.session.query(
            func.date(SyncRecord.timestamp).label('date'),
            func.count(SyncRecord.id).label('count'),
            SyncRecord.status
        ).filter(
            SyncRecord.user_id == user_id,
            SyncRecord.timestamp >= start_date
        ).group_by(
            func.date(SyncRecord.timestamp),
            SyncRecord.status
        ).order_by(
            func.date(SyncRecord.timestamp)
        )
        
        results = query.all()
        
        # Process into format for charting
        dates = set()
        status_counts = {}
        
        for date, count, status in results:
            date_str = date.strftime('%Y-%m-%d')
            dates.add(date_str)
            
            if status not in status_counts:
                status_counts[status] = {}
            
            status_counts[status][date_str] = count
        
        # Convert to lists for charting
        dates_list = sorted(list(dates))
        
        chart_data = {
            'labels': dates_list,
            'successful': [status_counts.get('success', {}).get(date, 0) for date in dates_list],
            'failed': [status_counts.get('error', {}).get(date, 0) for date in dates_list],
        }
        
        return chart_data
    
    def count_syncs_for_user(self, user_id, status=None):
        """Count sync records for a user.
        
        Args:
            user_id: User ID
            status: Optional status filter
            
        Returns:
            Integer count
        """
        query = SyncRecord.query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
            
        return query.count()
