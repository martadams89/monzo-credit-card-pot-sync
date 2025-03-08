"""Service for managing account baselines"""

import logging
import time

log = logging.getLogger("baseline_service")

class BaselineService:
    """Service for managing account baseline operations"""
    
    def __init__(self, account_repository, db_session):
        self.account_repository = account_repository
        self.db = db_session
    
    def update_account_baselines(self, credit_accounts):
        """
        Update account baselines - corresponds to SECTION 7
        For accounts not in cooldown, update the persisted baseline with current card balance
        """
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
                
                # Don't update baselines when in cooldown
                if credit_account.cooldown_until and current_time < credit_account.cooldown_until:
                    log.info(f"[Baseline Update] {credit_account.type}: Cooldown active; baseline not updated.")
                    continue
                    
                if live != prev:
                    self._update_baseline(credit_account, live, prev)
                else:
                    log.info(f"[Baseline Update] {credit_account.type}: Baseline remains unchanged (prev: £{prev / 100:.2f}, live: £{live / 100:.2f}).")
    
    def _update_baseline(self, credit_account, live, prev):
        """Update an account's baseline value"""
        log.info(f"[Baseline Update] {credit_account.type}: Updating baseline from £{prev / 100:.2f} to £{live / 100:.2f}.")
        self.account_repository.update_credit_account_fields(
            credit_account.type, 
            credit_account.pot_id, 
            live, 
            credit_account.cooldown_until
        )
        self.db.session.commit()
        credit_account.prev_balance = live
