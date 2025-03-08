"""Service for handling balance calculations and adjustments"""

import logging
from sqlalchemy.exc import NoResultFound
from app.domain.settings import Setting
from app.utils.api_helpers import validate_balance_change

log = logging.getLogger("balance_service")

class BalanceService:
    """Service for managing balance calculations and adjustments"""
    
    def __init__(self, account_repository, settings_repository):
        self.account_repository = account_repository
        self.settings_repository = settings_repository
    
    def calculate_pot_balances(self, monzo_account, credit_accounts):
        """
        Calculate balance differentials per pot - SECTION 3
        Returns a mapping of pot_id -> balance_info
        """
        pot_balance_map = {}
        for credit_account in credit_accounts:
            try:
                pot_id = credit_account.pot_id
                if not pot_id:
                    raise NoResultFound(f"No designated credit card pot set for {credit_account.type}")
                    
                account_selection = monzo_account.get_account_type(pot_id)
                if pot_id not in pot_balance_map:
                    log.info(f"Retrieving balance for credit card pot {pot_id}")
                    pot_balance = monzo_account.get_pot_balance(pot_id)
                    pot_balance_map[pot_id] = {
                        'balance': pot_balance,
                        'account_selection': account_selection,
                        'credit_type': credit_account.type
                    }
                    log.info(f"Credit card pot {pot_id} balance is £{pot_balance / 100:.2f}")
            except NoResultFound:
                log.error(f"No designated credit card pot configured for {credit_account.type}")
                raise
            
            log.info(f"Retrieving balance for {credit_account.type} credit card")
            credit_balance = credit_account.get_total_balance(force_refresh=True)
            log.info(f"{credit_account.type} card balance is £{credit_balance / 100:.2f}")
            
            # Validate the balance change
            if not validate_balance_change(credit_account.type, credit_account.prev_balance, credit_balance):
                log.warning(f"Suspicious balance change detected for {credit_account.type}, skipping")
                continue
                
            pot_balance_map[credit_account.pot_id]['balance'] -= credit_balance

        return pot_balance_map
        
    def add_to_pot(self, monzo_account, credit_account, amount, reason="deposit"):
        """
        Safely add funds to a pot with balance checking - Part of SECTION 6
        Returns (success, new_balance) tuple
        """
        selection = monzo_account.get_account_type(credit_account.pot_id)
        available_funds = monzo_account.get_balance(selection)
        
        if available_funds < amount:
            insufficient_diff = amount - available_funds
            log.error(f"Insufficient funds in Monzo account to sync pot; required: £{amount/100:.2f}, available: £{available_funds/100:.2f}; diff required £{insufficient_diff/100:.2f}; disabling sync")
            self.settings_repository.save(Setting("enable_sync", "False"))
            monzo_account.send_notification(
                f"Lacking £{insufficient_diff/100:.2f} - Insufficient Funds, Sync Disabled",
                f"Sync disabled due to insufficient funds. Required deposit: £{amount/100:.2f}, available: £{available_funds/100:.2f}. Please top up at least £{insufficient_diff/100:.2f} and re-enable sync.",
                account_selection=selection
            )
            return False, None
            
        monzo_account.add_to_pot(credit_account.pot_id, amount, account_selection=selection)
        new_pot_balance = monzo_account.get_pot_balance(credit_account.pot_id)
        
        log.info(f"{reason}: Added £{amount/100:.2f} to pot for {credit_account.type}. New balance: £{new_pot_balance/100:.2f}")
        return True, new_pot_balance
    
    def withdraw_from_pot(self, monzo_account, credit_account, amount, reason="withdrawal"):
        """
        Safely withdraw funds from a pot - Part of SECTION 6
        Returns new pot balance
        """
        selection = monzo_account.get_account_type(credit_account.pot_id)
        monzo_account.withdraw_from_pot(credit_account.pot_id, amount, account_selection=selection)
        new_pot_balance = monzo_account.get_pot_balance(credit_account.pot_id)
        
        log.info(f"{reason}: Withdrew £{amount/100:.2f} from pot for {credit_account.type}. New balance: £{new_pot_balance/100:.2f}")
        return new_pot_balance
