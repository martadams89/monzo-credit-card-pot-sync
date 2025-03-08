"""Service for tracking and recording sync metrics and history"""

import logging
import datetime
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository

log = logging.getLogger("metrics_service")

class MetricsService:
    """Tracks metrics and records sync history"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.history_repository = SqlAlchemySyncHistoryRepository(db_session)
        self.metrics = self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Initialize metrics structure"""
        return {
            "started_at": datetime.datetime.now(),
            "status": "in_progress",
            "accounts_processed": [],
            "errors": []
        }
    
    def record_account_success(self, account_type, balance, pot_balance):
        """Record successful account processing"""
        self.metrics["accounts_processed"].append({
            "account": account_type,
            "status": "success",
            "balance": balance,
            "pot_balance": pot_balance
        })
    
    def record_account_error(self, account_type, error_message):
        """Record account processing error"""
        self.metrics["accounts_processed"].append({
            "account": account_type,
            "status": "error",
            "error_message": error_message
        })
        self.metrics["errors"].append({
            "account": account_type,
            "error": error_message
        })
    
    def record_account_action(self, account_type, action_type, amount, balance):
        """Record a specific account action (deposit or withdrawal)"""
        # This could be expanded to record more detailed metrics
        pass
    
    def finalize_sync(self, status, error_message=None):
        """Finalize the sync and record history"""
        self.metrics["status"] = status
        
        if error_message:
            self.metrics["errors"].append({
                "global": True,
                "error": error_message
            })
        
        log.info(f"Sync completed with status: {status}")
        
        # Store sync history
        try:
            self.history_repository.save_sync_result(self.metrics)
            log.info("Sync history recorded.")
        except Exception as e:
            log.error(f"Failed to record sync history: {e}")
            
        return self.metrics
