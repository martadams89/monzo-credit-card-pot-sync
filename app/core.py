"""
Core application logic for Monzo Credit Card Pot Sync.

This module contains the core business logic for synchronizing credit card balances
with Monzo pots. It serves as a higher-level layer above the individual services,
coordinating their functionality.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.account_service import AccountService
from app.services.sync_service import SyncService
from app.services.balance_service import BalanceService
from app.services.cooldown_service import CooldownService
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository

# Set up logging
log = logging.getLogger(__name__)

# Global service instances
account_service = None
balance_service = None
cooldown_service = None
sync_service = None
history_repository = None

def init_services(db_session, setting_repository=None):
    """Initialize all required services.
    
    Args:
        db_session: SQLAlchemy database session
        setting_repository: Optional repository for application settings
    """
    global account_service, balance_service, cooldown_service, sync_service, history_repository
    
    # Initialize repositories first
    from app.models.account_repository import SqlAlchemyAccountRepository
    from app.models.cooldown_repository import SqlAlchemyCooldownRepository
    
    account_repository = SqlAlchemyAccountRepository(db_session)
    cooldown_repository = SqlAlchemyCooldownRepository(db_session)
    history_repository = SqlAlchemySyncHistoryRepository(db_session)
    
    # Initialize services
    account_service = AccountService(db_session, account_repository, None, None, setting_repository)
    balance_service = BalanceService(None, None, setting_repository)
    cooldown_service = CooldownService(db_session, cooldown_repository)
    
    # Initialize sync service last, as it depends on the other services
    sync_service = SyncService(account_service, balance_service, cooldown_service, history_repository)
    
    log.info("Core services initialized")

def sync_all_accounts() -> Dict[str, Any]:
    """Synchronize all configured accounts.
    
    This function triggers a synchronization of all accounts across all users.
    
    Returns:
        dict: Result of the sync operation
    """
    if not sync_service:
        log.error("Services not initialized. Call init_services() first")
        return {"status": "error", "message": "Services not initialized"}
    
    log.info("Syncing all accounts")
    try:
        result = sync_service.sync_all_accounts()
        return result
    except Exception as e:
        log.error(f"Error syncing accounts: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Error: {str(e)}"}

def sync_user_accounts(user_id: int) -> Dict[str, Any]:
    """Synchronize accounts for a specific user.
    
    Args:
        user_id: User ID
    
    Returns:
        dict: Result of the sync operation
    """
    if not sync_service:
        log.error("Services not initialized. Call init_services() first")
        return {"status": "error", "message": "Services not initialized"}
    
    log.info(f"Syncing accounts for user {user_id}")
    try:
        result = sync_service.sync_all_accounts(user_id)
        return result
    except Exception as e:
        log.error(f"Error syncing accounts for user {user_id}: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Error: {str(e)}"}

def get_sync_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent synchronization history.
    
    Args:
        limit: Maximum number of records to return
    
    Returns:
        list: Recent sync history entries
    """
    if not history_repository:
        log.error("Services not initialized. Call init_services() first")
        return []
    
    try:
        return history_repository.get_recent_syncs(limit)
    except Exception as e:
        log.error(f"Error retrieving sync history: {str(e)}")
        return []

def clear_account_cooldown(account_id: str) -> bool:
    """Clear cooldown period for an account.
    
    Args:
        account_id: External account ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not cooldown_service:
        log.error("Services not initialized. Call init_services() first")
        return False
    
    try:
        count = cooldown_service.clear_cooldown(account_id=account_id)
        return count > 0
    except Exception as e:
        log.error(f"Error clearing cooldown for account {account_id}: {str(e)}")
        return False

def get_sync_status() -> Dict[str, Any]:
    """Get the current synchronization status.
    
    Returns:
        dict: Synchronization status information
    """
    if not history_repository:
        return {
            "status": "unknown",
            "last_sync": None,
            "success_rate": None,
            "accounts_synced": 0
        }
    
    try:
        # Get the most recent sync record
        recent_syncs = history_repository.get_recent_syncs(5)
        
        if not recent_syncs:
            return {
                "status": "inactive",
                "last_sync": None,
                "success_rate": None,
                "accounts_synced": 0
            }
        
        latest_sync = recent_syncs[0]
        
        # Calculate success rate from recent syncs
        success_count = sum(1 for sync in recent_syncs if sync["status"] in ["completed", "partial"])
        success_rate = (success_count / len(recent_syncs)) * 100 if recent_syncs else 0
        
        # Determine status based on last sync
        status = "active" if latest_sync["status"] in ["completed", "partial"] else "error"
        
        # Count synced accounts from last sync
        accounts_synced = 0
        if latest_sync.get("data") and "accounts_processed" in latest_sync["data"]:
            accounts_processed = latest_sync["data"]["accounts_processed"]
            accounts_synced = sum(1 for acc in accounts_processed if acc.get("status") == "success")
        
        return {
            "status": status,
            "last_sync": latest_sync["timestamp"],
            "success_rate": success_rate,
            "accounts_synced": accounts_synced
        }
        
    except Exception as e:
        log.error(f"Error getting sync status: {str(e)}")
        return {
            "status": "error",
            "last_sync": None,
            "success_rate": None,
            "accounts_synced": 0,
            "error": str(e)
        }