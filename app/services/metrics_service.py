"""
Service for collecting and analyzing application metrics.

This service provides functionality to track various metrics about the application's
performance, sync operations, and user activities.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

class MetricsService:
    """Service for collecting and analyzing application metrics."""
    
    def __init__(self, db_session=None, sync_history_repository=None, setting_repository=None):
        """Initialize MetricsService.
        
        Args:
            db_session: SQLAlchemy database session
            sync_history_repository: Repository for sync history records
            setting_repository: Repository for app settings
        """
        self.db = db_session
        self.sync_history_repository = sync_history_repository
        self.setting_repository = setting_repository
    
    def get_sync_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get metrics about synchronization operations.
        
        Args:
            days: Number of days to include in metrics
            
        Returns:
            dict: Sync metrics
        """
        try:
            if not self.sync_history_repository:
                return {"error": "No sync history repository available"}
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get sync history for period
            syncs = self.sync_history_repository.get_syncs_in_range(start_date, end_date)
            
            if not syncs:
                return {
                    "total_syncs": 0,
                    "success_rate": 0,
                    "average_duration_ms": 0,
                    "deposits": 0,
                    "withdrawals": 0,
                    "total_moved": 0,
                    "by_day": [],
                    "by_status": {"completed": 0, "partial": 0, "failed": 0, "error": 0, "no_accounts": 0}
                }
            
            # Calculate metrics
            total_syncs = len(syncs)
            success_count = sum(1 for sync in syncs if sync["status"] in ["completed", "partial"])
            success_rate = (success_count / total_syncs) * 100 if total_syncs else 0
            
            # Process accounts
            deposits = 0
            withdrawals = 0
            total_amount = 0
            
            for sync in syncs:
                if not sync.get("data") or "accounts_processed" not in sync["data"]:
                    continue
                
                accounts = sync["data"]["accounts_processed"]
                for account in accounts:
                    if account.get("action") == "deposit" and account.get("status") == "success":
                        deposits += 1
                        total_amount += account.get("amount", 0)
                    elif account.get("action") == "withdraw" and account.get("status") == "success":
                        withdrawals += 1
                        total_amount += account.get("amount", 0)
            
            # Group by day
            by_day = self._group_syncs_by_day(syncs, start_date, end_date)
            
            # Group by status
            by_status = {
                "completed": sum(1 for sync in syncs if sync["status"] == "completed"),
                "partial": sum(1 for sync in syncs if sync["status"] == "partial"),
                "failed": sum(1 for sync in syncs if sync["status"] == "failed"),
                "error": sum(1 for sync in syncs if sync["status"] == "error"),
                "no_accounts": sum(1 for sync in syncs if sync["status"] == "no_accounts")
            }
            
            return {
                "total_syncs": total_syncs,
                "success_rate": success_rate,
                "deposits": deposits,
                "withdrawals": withdrawals,
                "total_moved": total_amount,
                "by_day": by_day,
                "by_status": by_status
            }
            
        except Exception as e:
            log.error(f"Error getting sync metrics: {str(e)}")
            return {"error": str(e)}
    
    def _group_syncs_by_day(self, syncs, start_date, end_date):
        """Group sync operations by day.
        
        Args:
            syncs: List of sync operations
            start_date: Start date for grouping
            end_date: End date for grouping
            
        Returns:
            list: Daily sync counts
        """
        # Create a dict with dates as keys
        day_counts = {}
        current_date = start_date
        while current_date <= end_date:
            day_key = current_date.strftime('%Y-%m-%d')
            day_counts[day_key] = {
                "date": day_key,
                "total": 0,
                "success": 0,
                "failure": 0
            }
            current_date += timedelta(days=1)
        
        # Count syncs by day
        for sync in syncs:
            if not sync.get("timestamp"):
                continue
                
            sync_date = sync["timestamp"]
            if isinstance(sync_date, str):
                try:
                    sync_date = datetime.fromisoformat(sync_date)
                except ValueError:
                    continue
                    
            day_key = sync_date.strftime('%Y-%m-%d')
            if day_key in day_counts:
                day_counts[day_key]["total"] += 1
                if sync["status"] in ["completed", "partial"]:
                    day_counts[day_key]["success"] += 1
                else:
                    day_counts[day_key]["failure"] += 1
        
        # Convert to list sorted by date
        return [day_counts[key] for key in sorted(day_counts.keys())]
    
    def get_user_metrics(self) -> Dict[str, Any]:
        """Get metrics about users and accounts.
        
        Returns:
            dict: User metrics
        """
        try:
            if not self.db:
                return {"error": "No database session available"}
            
            # Get user counts
            from app.models.user import User
            from app.models.account import Account
            
            user_count = User.query.count()
            active_user_count = User.query.filter_by(is_active=True).count()
            admin_count = User.query.filter_by(is_admin=True).count()
            
            # Get account counts
            account_count = Account.query.count()
            account_types = {}
            
            # Count accounts by type
            account_query = self.db.session.query(Account.type, db.func.count(Account.id))
            account_query = account_query.group_by(Account.type)
            for account_type, count in account_query.all():
                account_types[account_type] = count
            
            # Calculate accounts per user
            accounts_per_user = account_count / user_count if user_count > 0 else 0
            
            return {
                "users": {
                    "total": user_count,
                    "active": active_user_count,
                    "admin": admin_count
                },
                "accounts": {
                    "total": account_count,
                    "per_user": accounts_per_user,
                    "by_type": account_types
                }
            }
            
        except Exception as e:
            log.error(f"Error getting user metrics: {str(e)}")
            return {"error": str(e)}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system and operational metrics.
        
        Returns:
            dict: System metrics
        """
        try:
            metrics = {
                "database": self._get_database_metrics(),
                "api": self._get_api_metrics()
            }
            
            return metrics
            
        except Exception as e:
            log.error(f"Error getting system metrics: {str(e)}")
            return {"error": str(e)}
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database metrics.
        
        Returns:
            dict: Database metrics
        """
        if not self.db:
            return {"status": "unknown"}
            
        try:
            # Check database connectivity
            self.db.session.execute("SELECT 1")
            
            # Get table sizes
            # This is a simple approach, won't work with all DB types
            tables = {}
            from app.models.user import User
            from app.models.account import Account
            
            tables["users"] = User.query.count()
            tables["accounts"] = Account.query.count()
            
            return {
                "status": "connected",
                "tables": tables
            }
            
        except Exception as e:
            log.error(f"Database metrics error: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _get_api_metrics(self) -> Dict[str, Any]:
        """Get API usage metrics.
        
        Returns:
            dict: API metrics
        """
        # API metrics would require more complex tracking
        # For now, return placeholder values
        return {
            "monzo_calls": {
                "today": 0,
                "rate_limit": "Unknown"
            },
            "truelayer_calls": {
                "today": 0,
                "rate_limit": "Unknown"
            }
        }
