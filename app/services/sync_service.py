"""Service for handling the core sync process"""

import logging
import time
import datetime
import traceback
from collections import Counter
from sqlalchemy.exc import NoResultFound

from app.domain.settings import Setting
from app.services.account_service import AccountService
from app.services.balance_service import BalanceService
from app.services.cooldown_service import CooldownService
from app.services.metrics_service import MetricsService
from app.services.account_processing_service import AccountProcessingService
from app.services.cooldown_processing_service import CooldownProcessingService
from app.services.baseline_service import BaselineService

"""
Core Sync Process Overview:

SECTION 1: INITIALIZATION AND CONNECTION VALIDATION
    - Retrieve and validate the Monzo account.
    - Refresh token if necessary and ping the connection.

SECTION 2: RETRIEVE AND VALIDATE CREDIT ACCOUNTS
    - Retrieve credit card connections.
    - Refresh tokens and validate health.
    - Remove accounts with auth issues.

SECTION 3: CALCULATE BALANCE DIFFERENTIALS PER POT
    - Build a mapping of pots with their live balance minus credit card balances.

SECTION 4: REFRESH PERSISTED ACCOUNT DATA
    - Reload each credit account's persisted fields (cooldown, prev_balance).

SECTION 5: EXPIRED COOLDOWN CHECK
    - For accounts with an expired cooldown, compute the shortfall.
      Branch: If shortfall exists, deposit it and clear cooldown; otherwise, simply clear cooldown.

SECTION 6: PER-ACCOUNT BALANCE ADJUSTMENT PROCESSING (DEPOSIT / WITHDRAWAL)
    - Process each credit account sequentially:
         (a) OVERRIDE BRANCH: If override flag is enabled and cooldown is active,
             deposit the difference immediately if card balance > previous balance.
         (b) STANDARD ADJUSTMENT: Compare live card vs. pot balance.
             – Deposit if card > pot.
             – Withdraw if card < pot.
             – Do nothing if equal.

SECTION 7: UPDATE BASELINE PERSISTENCE
    - For each account, if a confirmed change is detected (card balance ≠ previous balance) and not in cooldown,
      update the persisted baseline with the current card balance.
"""

log = logging.getLogger("sync_service")

class SyncService:
    """Main service that orchestrates the sync process"""
    
    def __init__(self, db_session, account_repository, settings_repository, 
                 account_service=None, balance_service=None, cooldown_service=None):
        self.db = db_session
        self.account_repository = account_repository
        self.settings_repository = settings_repository
        
        # Initialize sub-services
        self.account_service = account_service or AccountService(account_repository, settings_repository)
        self.balance_service = balance_service or BalanceService(account_repository, settings_repository)
        self.cooldown_service = cooldown_service or CooldownService(account_repository, db_session, settings_repository)
        
        # Initialize specialized processing services
        self.metrics_service = MetricsService(db_session)
        self.account_processor = AccountProcessingService(
            account_repository, 
            self.balance_service, 
            self.cooldown_service,
            settings_repository, 
            db_session
        )
        self.cooldown_processor = CooldownProcessingService(
            account_repository, 
            self.balance_service, 
            self.cooldown_service, 
            db_session,
            self.metrics_service
        )
        self.baseline_service = BaselineService(account_repository, db_session)
        
    def run_sync(self):
        """Run the complete sync process"""
        try:
            # SECTION 1: INITIALIZATION AND CONNECTION VALIDATION
            monzo_account = self.account_service.initialize_monzo_account()
            if monzo_account is None:
                self.metrics_service.finalize_sync("failed", "No Monzo account available")
                return
                
            # SECTION 2: RETRIEVE AND VALIDATE CREDIT ACCOUNTS
            credit_accounts = self.account_service.get_credit_accounts(monzo_account)
            if not credit_accounts:
                self.metrics_service.finalize_sync("failed", "No valid credit accounts available")
                return
                
            # Check if sync is enabled
            if not self.settings_repository.get("enable_sync"):
                log.info("Balance sync is disabled; exiting sync loop")
                self.metrics_service.finalize_sync("skipped", "Sync is disabled")
                return
                
            # SECTION 3: CALCULATE BALANCE DIFFERENTIALS PER POT
            try:
                pot_balance_map = self.balance_service.calculate_pot_balances(monzo_account, credit_accounts)
                if not pot_balance_map:
                    self.metrics_service.finalize_sync("failed", "Failed to calculate pot balances")
                    return
            except NoResultFound as e:
                self.metrics_service.finalize_sync("failed", str(e))
                return
                
            # SECTION 4: REFRESH PERSISTED ACCOUNT DATA
            credit_accounts = self.cooldown_service.refresh_account_data(credit_accounts)
                
            # SECTION 5: EXPIRED COOLDOWN CHECK
            self.cooldown_processor.process_cooldowns(monzo_account, credit_accounts)
                
            # SECTION 6: PER-ACCOUNT BALANCE ADJUSTMENT PROCESSING
            self._process_balance_adjustments(monzo_account, credit_accounts)
                
            # SECTION 7: UPDATE BASELINE PERSISTENCE
            self.baseline_service.update_account_baselines(credit_accounts)
                
            # Finalize the sync
            self.metrics_service.finalize_sync("completed")
            
        except Exception as e:
            error_info = traceback.format_exc()
            log.error(f"Sync error: {e}\n{error_info}")
            self.metrics_service.finalize_sync("failed", str(e))
            raise
    
    def _process_balance_adjustments(self, monzo_account, credit_accounts):
        """Process balance adjustments for each account - corresponds to SECTION 6"""
        # Retrieve override setting once and convert to boolean
        override_value = self.settings_repository.get("override_cooldown_spending")
        if isinstance(override_value, bool):
            override_cooldown_spending = override_value
        else:
            override_cooldown_spending = override_value.lower() == "true"
        log.info(f"override_cooldown_spending is '{override_value}' -> {override_cooldown_spending}")
        
        for credit_account in credit_accounts:
            # Refresh account data
            self.db.session.commit()
            if hasattr(credit_account, "_sa_instance_state"):
                self.db.session.expire(credit_account)
            refreshed = self.account_repository.get(credit_account.type)
            credit_account.cooldown_until = refreshed.cooldown_until
            credit_account.prev_balance = refreshed.prev_balance
            
            log.info("-------------------------------------------------------------")
            log.info(f"Step: Start processing account '{credit_account.type}'.")

            # Retrieve current live figures
            live_card_balance = credit_account.get_total_balance(force_refresh=True)
            current_pot = monzo_account.get_pot_balance(credit_account.pot_id)
            stable_pot = credit_account.stable_pot_balance if credit_account.stable_pot_balance is not None else 0

            # Log current account status
            self._log_account_status(credit_account, live_card_balance, current_pot, stable_pot)

            try:
                now = int(time.time())
                
                # OVERRIDE BRANCH
                if override_cooldown_spending and (credit_account.cooldown_until is not None and now < credit_account.cooldown_until):
                    self.account_processor.process_override_branch(monzo_account, credit_account, live_card_balance, current_pot)
                
                # STANDARD ADJUSTMENT
                if credit_account.cooldown_until is None or now > credit_account.cooldown_until:
                    self.account_processor.process_standard_adjustment(monzo_account, credit_account, live_card_balance, current_pot)
                
                # Record successful processing
                self.metrics_service.record_account_success(credit_account.type, live_card_balance, current_pot)
                
            except Exception as e:
                log.error(f"Error processing account {credit_account.type}: {e}", exc_info=True)
                self.metrics_service.record_account_error(credit_account.type, str(e))
            
            log.info(f"Step: Finished processing account '{credit_account.type}'.")
            log.info("-------------------------------------------------------------")
    
    def _log_account_status(self, credit_account, live_card_balance, current_pot, stable_pot):
        """Log the current status of an account"""
        log.info(
            f"Account '{credit_account.type}': Live Card Balance = £{live_card_balance / 100:.2f}; "
            f"Previous Card Baseline = £{credit_account.prev_balance / 100:.2f}."
        )
        log.info(
            f"Pot '{credit_account.pot_id}': Current Pot Balance = £{current_pot / 100:.2f}; "
            f"Stable Pot Balance = £{stable_pot / 100:.2f}."
        )
        
        now = int(time.time())
        if credit_account.cooldown_until:
            hr_cooldown = datetime.datetime.fromtimestamp(credit_account.cooldown_until).strftime("%Y-%m-%d %H:%M:%S")
            if now < credit_account.cooldown_until:
                log.info(f"Cooldown active until {hr_cooldown} (epoch: {credit_account.cooldown_until}).")
            else:
                log.info(f"Cooldown expired at {hr_cooldown} (epoch: {credit_account.cooldown_until}).")
        else:
            log.info("No active cooldown on this account.")
    
    def _update_account_baselines(self, credit_accounts):
        """Update account baselines - corresponds to SECTION 7"""
        current_time = int(time.time())
        for credit_account in credit_accounts:
            self.db.session.commit()
            if hasattr(credit_account, "_sa_instance_state"):
                self.db.session.expire(credit_account)
            refreshed = self.account_repository.get(credit_account.type)
            # Ensure we have the latest prev_balance
            credit_account.prev_balance = refreshed.prev_balance
            
            if credit_account.pot_id:
                live = credit_account.get_total_balance(force_refresh=False)
                prev = credit_account.get_prev_balance(credit_account.pot_id)
                if credit_account.cooldown_until and current_time < credit_account.cooldown_until:
                    log.info(f"[Baseline Update] {credit_account.type}: Cooldown active; baseline not updated.")
                    continue
                    
                if live != prev:
                    log.info(f"[Baseline Update] {credit_account.type}: Updating baseline from £{prev / 100:.2f} to £{live / 100:.2f}.")
                    self.account_repository.update_credit_account_fields(credit_account.type, credit_account.pot_id, live, credit_account.cooldown_until)
                    self.db.session.commit()
                    credit_account.prev_balance = live
                else:
                    log.info(f"[Baseline Update] {credit_account.type}: Baseline remains unchanged (prev: £{prev / 100:.2f}, live: £{live / 100:.2f}).")
