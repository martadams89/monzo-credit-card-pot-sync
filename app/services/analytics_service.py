"""Service for generating analytics data"""

import logging
import json
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy import func, desc, and_

log = logging.getLogger("analytics_service")

class AnalyticsService:
    """Service for generating analytics and dashboard data"""
    
    def __init__(self, db_session, sync_history_repository):
        self.db = db_session
        self.sync_history_repository = sync_history_repository
    
    def get_sync_statistics(self, days=7):
        """Get sync statistics for the dashboard"""
        # Define the time range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get sync history for the period
        history = self.sync_history_repository.get_sync_history(start_date, end_date)
        
        # Process the data
        stats = {
            "total_syncs": len(history),
            "success_rate": 0,
            "failure_rate": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "skipped_syncs": 0,
            "status_counts": {},
            "daily_counts": {},
            "common_errors": {},
            "account_stats": {}
        }
        
        # Calculate daily statistics
        date_range = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
        for date in date_range:
            stats["daily_counts"][date] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0
            }
        
        # Process each sync record
        if history:
            all_errors = []
            account_actions = {}
            
            for sync in history:
                # Get sync data
                sync_data = json.loads(sync.data) if isinstance(sync.data, str) else sync.data
                sync_date = sync.created_at.strftime('%Y-%m-%d')
                
                # Update status counts
                status = sync_data.get("status", "unknown")
                stats["status_counts"][status] = stats["status_counts"].get(status, 0) + 1
                
                # Update success/failure counts
                if status == "completed":
                    stats["successful_syncs"] += 1
                elif status == "skipped":
                    stats["skipped_syncs"] += 1
                else:
                    stats["failed_syncs"] += 1
                
                # Update daily counts
                if sync_date in stats["daily_counts"]:
                    stats["daily_counts"][sync_date]["total"] += 1
                    if status == "completed":
                        stats["daily_counts"][sync_date]["successful"] += 1
                    elif status == "skipped":
                        stats["daily_counts"][sync_date]["skipped"] += 1
                    else:
                        stats["daily_counts"][sync_date]["failed"] += 1
                
                # Collect errors
                for error in sync_data.get("errors", []):
                    error_msg = error.get("error", "Unknown error")
                    all_errors.append(error_msg)
                
                # Process account actions
                for account in sync_data.get("accounts_processed", []):
                    account_name = account.get("account")
                    if not account_name:
                        continue
                        
                    if account_name not in account_actions:
                        account_actions[account_name] = {
                            "deposits": 0,
                            "withdrawals": 0,
                            "deposit_amount": 0,
                            "withdrawal_amount": 0,
                            "current_balance": account.get("balance", 0),
                            "current_pot_balance": account.get("pot_balance", 0),
                            "success_count": 0,
                            "error_count": 0
                        }
                    
                    if account.get("status") == "success":
                        account_actions[account_name]["success_count"] += 1
                    else:
                        account_actions[account_name]["error_count"] += 1
                        
                    # Look for deposit/withdrawal actions
                    for action in account.get("actions", []):
                        action_type = action.get("type")
                        amount = action.get("amount", 0)
                        
                        if action_type == "deposit":
                            account_actions[account_name]["deposits"] += 1
                            account_actions[account_name]["deposit_amount"] += amount
                        elif action_type == "withdrawal":
                            account_actions[account_name]["withdrawals"] += 1
                            account_actions[account_name]["withdrawal_amount"] += amount
            
            # Calculate success and failure rates
            if stats["total_syncs"] > 0:
                stats["success_rate"] = round((stats["successful_syncs"] / stats["total_syncs"]) * 100, 1)
                stats["failure_rate"] = round((stats["failed_syncs"] / stats["total_syncs"]) * 100, 1)
            
            # Find common errors
            if all_errors:
                error_counter = Counter(all_errors)
                stats["common_errors"] = {error: count for error, count in error_counter.most_common(5)}
            
            # Set account statistics
            stats["account_stats"] = account_actions
        
        return stats
    
    def get_transaction_history(self, days=30, account_type=None):
        """Get transaction history for dashboard"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        history = self.sync_history_repository.get_detailed_sync_history(start_date, end_date, account_type)
        
        transactions = []
        for record in history:
            sync_data = json.loads(record.data) if isinstance(record.data, str) else record.data
            
            for account in sync_data.get("accounts_processed", []):
                if account_type and account.get("account") != account_type:
                    continue
                
                for action in account.get("actions", []):
                    transactions.append({
                        "date": record.created_at,
                        "account": account.get("account"),
                        "action": action.get("type"),
                        "amount": action.get("amount"),
                        "balance_after": action.get("balance_after"),
                        "reason": action.get("reason", "")
                    })
        
        return transactions
    
    def get_spending_trends(self, days=90):
        """Get spending trends for the dashboard"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Define time frames
        today = end_date.date()
        week_ago = (end_date - timedelta(days=7)).date()
        month_ago = (end_date - timedelta(days=30)).date()
        
        history = self.sync_history_repository.get_sync_history(start_date, end_date)
        
        # Initialize trend data
        trends = {
            "total_spending": 0,
            "daily_average": 0,
            "weekly_trend": 0,  # percentage change
            "monthly_trend": 0,  # percentage change
            "by_account": {},
            "by_day": {},
            "by_week": {},
            "by_month": {}
        }
        
        # Process history
        if history:
            daily_spending = {}
            account_spending = {}
            
            for sync in history:
                sync_data = json.loads(sync.data) if isinstance(sync.data, str) else sync.data
                sync_date = sync.created_at.date()
                
                # Initialize date in daily spending
                if sync_date not in daily_spending:
                    daily_spending[sync_date] = 0
                
                # Process accounts
                for account in sync_data.get("accounts_processed", []):
                    account_name = account.get("account")
                    if not account_name:
                        continue
                    
                    # Initialize account in account spending
                    if account_name not in account_spending:
                        account_spending[account_name] = 0
                    
                    # Sum deposits (spending)
                    for action in account.get("actions", []):
                        if action.get("type") == "deposit":
                            amount = action.get("amount", 0)
                            daily_spending[sync_date] += amount
                            account_spending[account_name] += amount
                            trends["total_spending"] += amount
            
            # Calculate daily average
            if daily_spending:
                trends["daily_average"] = trends["total_spending"] / len(daily_spending)
            
            # Calculate trends by day, week, and month
            for date, amount in daily_spending.items():
                date_str = date.strftime("%Y-%m-%d")
                trends["by_day"][date_str] = amount
                
                # Week calculation
                week_num = date.isocalendar()[1]
                week_key = f"{date.year}-W{week_num}"
                if week_key not in trends["by_week"]:
                    trends["by_week"][week_key] = 0
                trends["by_week"][week_key] += amount
                
                # Month calculation
                month_key = date.strftime("%Y-%m")
                if month_key not in trends["by_month"]:
                    trends["by_month"][month_key] = 0
                trends["by_month"][month_key] += amount
            
            # Calculate weekly and monthly trends
            week_spending = sum(amount for date, amount in daily_spending.items() if date >= week_ago)
            prev_week_spending = sum(amount for date, amount in daily_spending.items() 
                                   if date < week_ago and date >= (week_ago - timedelta(days=7)))
            
            month_spending = sum(amount for date, amount in daily_spending.items() if date >= month_ago)
            prev_month_spending = sum(amount for date, amount in daily_spending.items() 
                                    if date < month_ago and date >= (month_ago - timedelta(days=30)))
            
            # Calculate percentage changes
            if prev_week_spending > 0:
                trends["weekly_trend"] = ((week_spending - prev_week_spending) / prev_week_spending) * 100
            
            if prev_month_spending > 0:
                trends["monthly_trend"] = ((month_spending - prev_month_spending) / prev_month_spending) * 100
            
            # Set spending by account
            trends["by_account"] = account_spending
        
        return trends
