"""Service for processing individual account transactions and adjustments"""

import logging
import time
import datetime

log = logging.getLogger("account_processing_service")

class AccountProcessingService:
    """Handles processing of individual account transactions"""
    
    def __init__(self, account_repository, balance_service, cooldown_service, settings_repository, db_session):
        self.account_repository = account_repository
        self.balance_service = balance_service
        self.cooldown_service = cooldown_service
        self.settings_repository = settings_repository
        self.db = db_session
        
    def process_override_branch(self, monzo_account, credit_account, live_card_balance, current_pot):
        """Process an account with override enabled during active cooldown"""
        log.info("Step: OVERRIDE branch activated due to cooldown flag.")
        selection = monzo_account.get_account_type(credit_account.pot_id)
        
        # Calculate deposit as the additional spending since the previous baseline
        diff = live_card_balance - credit_account.prev_balance
        if diff > 0:
            success, new_pot = self.balance_service.add_to_pot(
                monzo_account, 
                credit_account, 
                diff, 
                reason="override deposit"
            )
            
            if success:
                log.info(
                    f"[Override] {credit_account.type}: Override deposit of £{diff/100:.2f} executed "
                    f"as card increased from £{credit_account.prev_balance/100:.2f} to £{live_card_balance/100:.2f}."
                )
                # Update card baseline but keep the previous shortfall queued (cooldown remains active)
                credit_account.prev_balance = live_card_balance
                self.account_repository.save(credit_account)
                self.db.session.commit()
                
        if live_card_balance < current_pot:
            log.info(f"[Override] {credit_account.type}: Withdrawal due to pot exceeding card balance.")
            diff = current_pot - live_card_balance
            
            new_pot = self.balance_service.withdraw_from_pot(
                monzo_account, 
                credit_account, 
                diff, 
                reason="override withdrawal"
            )
            
            log.info(
                f"[Override] {credit_account.type}: Withdrew £{diff / 100:.2f} as pot exceeded card. "
                f"Pot changed from £{current_pot / 100:.2f} to £{new_pot / 100:.2f} while card remains at £{live_card_balance / 100:.2f}."
            )
            credit_account.prev_balance = live_card_balance
            self.account_repository.save(credit_account)
            
        log.info(f"Step: Finished OVERRIDE branch for account '{credit_account.type}'.")
        
    def process_standard_adjustment(self, monzo_account, credit_account, live_card_balance, current_pot):
        """Process standard balance adjustment for an account"""
        if live_card_balance < current_pot:
            self.handle_withdrawal(monzo_account, credit_account, live_card_balance, current_pot)
            
        elif live_card_balance > credit_account.prev_balance:
            self.handle_deposit(monzo_account, credit_account, live_card_balance, current_pot)
            
        elif live_card_balance == credit_account.prev_balance:
            if current_pot < live_card_balance:
                self.handle_pot_shortfall(monzo_account, credit_account, live_card_balance, current_pot)
            else:
                log.info(f"[Standard] {credit_account.type}: Card and pot balance unchanged; no action taken.")
    
    def handle_withdrawal(self, monzo_account, credit_account, live_card_balance, current_pot):
        """Handle withdrawal when pot balance exceeds card balance"""
        log.info("Step: Withdrawal due to pot exceeding card balance.")
        diff = current_pot - live_card_balance
        
        new_pot = self.balance_service.withdraw_from_pot(
            monzo_account, 
            credit_account, 
            diff, 
            reason="standard withdrawal"
        )
        
        log.info(
            f"[Standard] {credit_account.type}: Withdrew £{diff / 100:.2f} as pot exceeded card. "
            f"Pot changed from £{current_pot / 100:.2f} to £{new_pot / 100:.2f} while card remains at £{live_card_balance / 100:.2f}."
        )
        credit_account.prev_balance = live_card_balance
        self.account_repository.save(credit_account)
        
    def handle_deposit(self, monzo_account, credit_account, live_card_balance, current_pot):
        """Handle deposit when card balance increases"""
        log.info("Step: Regular spending detected (card balance increased).")
        diff = live_card_balance - current_pot
        
        success, new_pot = self.balance_service.add_to_pot(
            monzo_account, 
            credit_account, 
            diff, 
            reason="standard deposit"
        )
        
        if not success:
            return
            
        log.info(
            f"[Standard] {credit_account.type}: Deposited £{diff / 100:.2f}. "
            f"Pot updated from £{current_pot / 100:.2f} to £{new_pot / 100:.2f}; card increased from £{credit_account.prev_balance / 100:.2f} to £{live_card_balance / 100:.2f}."
        )
        credit_account.prev_balance = live_card_balance
        self.account_repository.update_credit_account_fields(
            credit_account.type,
            credit_account.pot_id,
            live_card_balance,
            credit_account.cooldown_until
        )
        self.db.session.commit()

    def handle_pot_shortfall(self, monzo_account, credit_account, live_card_balance, current_pot):
        """Handle pot shortfall when card balance is unchanged but pot balance is less"""
        log.info("Step: No increase in card balance detected.")
        
        if self.settings_repository.get("enable_sync") == "False":
            log.info(f"[Standard] {credit_account.type}: Sync disabled; not initiating cooldown.")
            return
            
        # Check for existing cooldown
        if credit_account.cooldown_until is not None:
            # Double-check persistence of the cooldown value
            self.db.session.commit()
            if hasattr(credit_account, "_sa_instance_state"):
                self.db.session.expire(credit_account)
            refreshed = self.account_repository.get(credit_account.type)
            now = int(time.time())
            if refreshed.cooldown_until and refreshed.cooldown_until > now:
                log.info(f"[Standard] {credit_account.type}: Cooldown already active; no new cooldown initiated.")
                return
            else:
                log.info("Persisted cooldown check not active; proceeding to initiate cooldown.")
                
        # Start new cooldown using the cooldown service
        log.info("Situation: Pot dropped below card balance without confirmed spending.")
        new_cooldown = self.cooldown_service.start_new_cooldown(credit_account)
        
        hr_cooldown = datetime.datetime.fromtimestamp(new_cooldown).strftime("%Y-%m-%d %H:%M:%S")
        log.info(
            f"[Standard] {credit_account.type}: Initiating cooldown because pot (£{current_pot / 100:.2f}) is less than card (£{live_card_balance / 100:.2f}). "
            f"Cooldown set until {hr_cooldown} (epoch: {new_cooldown})."
        )
        self.account_repository.save(credit_account)
        
        # Verify cooldown was saved correctly
        try:
            self.db.session.commit()
            refreshed = self.account_repository.get(credit_account.type)
            if refreshed.cooldown_until != new_cooldown:
                log.error(f"[Standard] {credit_account.type}: Cooldown persistence error: expected {new_cooldown}, got {refreshed.cooldown_until}.")
            else:
                log.info(f"[Standard] {credit_account.type}: Cooldown persisted successfully.")
        except Exception as e:
            self.db.session.rollback()
            log.error(f"[Standard] {credit_account.type}: Error committing cooldown to database: {e}")
