import logging
from sqlalchemy.exc import SQLAlchemyError
from app.models.sync_history import SyncHistory
import datetime
import json

log = logging.getLogger(__name__)

class SqlAlchemySyncHistoryRepository:
    def __init__(self, db):
        self.db = db
    
    def save_sync_result(self, sync_result):
        """Save sync result to history"""
        try:
            # Ensure we're not passing any complex objects that can't be serialized
            # Convert any datetime objects to strings in the data
            history = SyncHistory(
                status=sync_result.get("status", "unknown"),
                data=sync_result  # Our custom DateTimeEncoder will handle datetime objects
            )
            self.db.session.add(history)
            self.db.session.commit()
            return history
        except SQLAlchemyError as e:
            log.error(f"Error saving sync history: {e}")
            self.db.session.rollback()
            return None
    
    def get_recent_syncs(self, limit=10):
        """Get most recent sync history entries"""
        try:
            return SyncHistory.query.order_by(SyncHistory.timestamp.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            log.error(f"Error retrieving sync history: {e}")
            return []
    
    def get_balance_history(self, account_type, days=30):
        """Get balance history for specific account"""
        try:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
            history_records = SyncHistory.query.filter(
                SyncHistory.timestamp >= cutoff_date,
                SyncHistory.status == "completed"
            ).order_by(SyncHistory.timestamp.asc()).all()
            
            # Extract balance data for the specific account
            balance_data = []
            for record in history_records:
                data = record.data_json
                for account_data in data.get("accounts_processed", []):
                    if account_data.get("account") == account_type and account_data.get("status") == "success":
                        balance_data.append({
                            "timestamp": record.timestamp,
                            "card_balance": account_data.get("balance", 0),
                            "pot_balance": account_data.get("pot_balance", 0)
                        })
            
            return balance_data
        except SQLAlchemyError as e:
            log.error(f"Error retrieving balance history: {e}")
            return []
