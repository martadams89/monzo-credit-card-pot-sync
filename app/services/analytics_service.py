"""Service for analytics and dashboard data."""

import logging
import json
from datetime import datetime, timedelta

log = logging.getLogger("analytics_service")

class AnalyticsService:
    """Service for analytics and dashboard data."""
    
    def __init__(self, history_repository=None, account_service=None):
        """Initialize the analytics service.
        
        Args:
            history_repository: Repository for sync history
            account_service: Account service for account information
        """
        self.history_repository = history_repository
        self.account_service = account_service
        
    def get_dashboard_data(self):
        """Get data for the analytics dashboard.
        
        Returns:
            dict: Dashboard data including sync stats and account metrics
        """
        try:
            # Get sync history from the repository
            sync_records = []
            if self.history_repository:
                sync_records = self.history_repository.get_recent_syncs(30)  # Last 30 records
            
            # Process records into analytics data
            sync_stats = self._calculate_sync_stats(sync_records)
            account_metrics = self._calculate_account_metrics(sync_records)
            
            # Get active accounts
            accounts = []
            if self.account_service:
                accounts = self.account_service.get_all_accounts()
            
            return {
                'sync_stats': sync_stats,
                'account_metrics': account_metrics,
                'account_count': len(accounts),
                'last_sync': sync_records[0].created_at if sync_records else None,
                'balance_history': self._get_balance_history(sync_records)
            }
        except Exception as e:
            log.error(f"Error getting dashboard data: {e}", exc_info=True)
            return {
                'sync_stats': {},
                'account_metrics': {},
                'account_count': 0,
                'last_sync': None,
                'balance_history': []
            }
    
    def _calculate_sync_stats(self, sync_records):
        """Calculate sync statistics from history records.
        
        Args:
            sync_records: List of sync history records
            
        Returns:
            dict: Sync statistics
        """
        total_syncs = len(sync_records)
        successful_syncs = 0
        failed_syncs = 0
        
        for record in sync_records:
            try:
                data = json.loads(record.data)
                if data.get('status') == 'completed':
                    successful_syncs += 1
                else:
                    failed_syncs += 1
            except (json.JSONDecodeError, AttributeError):
                failed_syncs += 1
        
        return {
            'total': total_syncs,
            'successful': successful_syncs,
            'failed': failed_syncs,
            'success_rate': (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
        }
    
    def _calculate_account_metrics(self, sync_records):
        """Calculate metrics per account type.
        
        Args:
            sync_records: List of sync history records
            
        Returns:
            dict: Account metrics by type
        """
        account_metrics = {}
        
        for record in sync_records:
            try:
                data = json.loads(record.data)
                for account_data in data.get('accounts_processed', []):
                    account_type = account_data.get('account')
                    if not account_type:
                        continue
                        
                    if account_type not in account_metrics:
                        account_metrics[account_type] = {
                            'sync_count': 0,
                            'successful_syncs': 0,
                            'deposit_count': 0,
                            'withdrawal_count': 0,
                            'total_deposited': 0,
                            'total_withdrawn': 0
                        }
                    
                    metrics = account_metrics[account_type]
                    metrics['sync_count'] += 1
                    
                    if account_data.get('status') == 'success':
                        metrics['successful_syncs'] += 1
                        
                    for action in account_data.get('actions', []):
                        if action.get('type') == 'deposit':
                            metrics['deposit_count'] += 1
                            metrics['total_deposited'] += action.get('amount', 0)
                        elif action.get('type') == 'withdraw':
                            metrics['withdrawal_count'] += 1
                            metrics['total_withdrawn'] += action.get('amount', 0)
            except (json.JSONDecodeError, AttributeError) as e:
                log.warning(f"Error processing sync record: {e}")
        
        return account_metrics
    
    def _get_balance_history(self, sync_records):
        """Extract balance history from sync records.
        
        Args:
            sync_records: List of sync history records
            
        Returns:
            dict: Balance history data by account type
        """
        balance_history = {}
        
        for record in sync_records:
            try:
                timestamp = record.created_at
                data = json.loads(record.data)
                
                for account_data in data.get('accounts_processed', []):
                    account_type = account_data.get('account')
                    if not account_type or account_data.get('status') != 'success':
                        continue
                    
                    if account_type not in balance_history:
                        balance_history[account_type] = []
                    
                    balance_history[account_type].append({
                        'timestamp': timestamp,
                        'card_balance': account_data.get('balance', 0),
                        'pot_balance': account_data.get('pot_balance', 0)
                    })
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return balance_history
