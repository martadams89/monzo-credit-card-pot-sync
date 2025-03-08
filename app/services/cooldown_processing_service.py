"""Service for processing cooldown logic during synchronization"""

import logging
from datetime import datetime, timedelta

log = logging.getLogger("cooldown_processing_service")

class CooldownProcessingService:
    """Service for handling cooldown logic during account synchronization"""
    
    def __init__(self, cooldown_service, setting_repository):
        self.cooldown_service = cooldown_service
        self.setting_repository = setting_repository
        
    def process_cooldown(self, account_type, card_balance, pot_balance, has_new_spending):
        """Process cooldown logic for an account
        
        Args:
            account_type (str): Type of account being processed
            card_balance (int): Current card balance in pence
            pot_balance (int): Current pot balance in pence
            has_new_spending (bool): Whether there's been new spending
            
        Returns:
            tuple: (allow_deposit, reason)
        """
        # Get cooldown hours from settings
        cooldown_hours = int(self.setting_repository.get('deposit_cooldown_hours', 3))
        
        # Check if there's a shortfall
        shortfall = card_balance - pot_balance
        
        # If pot balance exceeds card balance, no cooldown needed
        if shortfall <= 0:
            return True, "Pot balance sufficient"
            
        # If there's new spending and override is enabled, allow deposit
        if has_new_spending and self._should_override_cooldown():
            return True, "New spending detected with override enabled"
            
        # Check if account is on cooldown
        if self.cooldown_service.is_account_on_cooldown(account_type):
            return False, f"Account on cooldown for {account_type}"
            
        # No cooldown, but shortfall exists - set cooldown and allow deposit now
        self.cooldown_service.set_cooldown(account_type, cooldown_hours)
        return True, "Initial shortfall detected, depositing and setting cooldown"
        
    def _should_override_cooldown(self):
        """Check if cooldown should be overridden for new spending"""
        return self.setting_repository.get('override_cooldown_spending', 'False') == 'True'
