"""
Main entry point for the credit card pot sync functionality.
This module orchestrates the synchronization of Monzo pots with credit card balances.
"""

import logging
import datetime

from app.extensions import db, scheduler
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository
from app.services.sync_service import SyncService
from app.services.account_service import AccountService
from app.services.balance_service import BalanceService
from app.services.cooldown_service import CooldownService

log = logging.getLogger("core")

def sync_balance():
    """
    Main entry point for the balance synchronization process.
    This orchestrates the overall sync workflow using service classes.
    """
    with scheduler.app.app_context():
        # Initialize repositories
        account_repository = SqlAlchemyAccountRepository(db)
        settings_repository = SqlAlchemySettingRepository(db)
        
        # Initialize services
        account_service = AccountService(account_repository, settings_repository)
        balance_service = BalanceService(account_repository, settings_repository)
        cooldown_service = CooldownService(account_repository, db, settings_repository)
        
        # Create the sync service that will orchestrate the process
        sync_service = SyncService(
            db_session=db, 
            account_repository=account_repository,
            settings_repository=settings_repository,
            account_service=account_service,
            balance_service=balance_service,
            cooldown_service=cooldown_service
        )
        
        # Execute the sync process
        try:
            sync_service.run_sync()
        except Exception as e:
            log.error(f"Sync process failed with error: {e}", exc_info=True)
            # Record sync error in history
            try:
                history_repository = SqlAlchemySyncHistoryRepository(db)
                history_repository.save_sync_result({
                    "started_at": datetime.datetime.now().isoformat(),
                    "status": "failed",
                    "error": str(e),
                    "accounts_processed": [],
                    "errors": [{
                        "global": True,
                        "error": str(e)
                    }]
                })
            except Exception as history_error:
                log.error(f"Failed to record sync history: {history_error}")