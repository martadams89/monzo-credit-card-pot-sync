"""
Service for processing and analyzing account data.

This service provides utilities for processing account data, including
analyzing balance changes, filtering accounts, and determining sync actions.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

log = logging.getLogger(__name__)

class AccountProcessingService:
    """Service for processing and analyzing account data."""
    
    def __init__(self, cooldown_service=None, balance_service=None, account_service=None):
        """Initialize AccountProcessingService.
        
        Args:
            cooldown_service: Service for managing cooldown periods
            balance_service: Service for retrieving balance information
            account_service: Service for managing accounts
        """
        self.cooldown_service = cooldown_service
        self.balance_service = balance_service
        self.account_service = account_service
    
    def analyze_account_data(self, accounts) -> List[Dict[str, Any]]:
        """Analyze account data to determine status and actions needed.
        
        Args:
            accounts: List of account objects
            
        Returns:
            list: Analysis results for each account
        """
        results = []
        
        for account in accounts:
            # Initialize result for this account
            result = {
                "account": account,
                "error": None,
                "card_balance": None,
                "pot_balance": None,
                "pot_needs_update": False,
                "update_amount": 0,
                "action_type": None,
                "cooldown_active": False,
                "cooldown_expires": None,
                "sync_percentage": 100,  # Default to 100% sync
                "last_synced": account.last_synced_at
            }
            
            # Check if account is in cooldown
            if self.cooldown_service and self.cooldown_service.is_in_cooldown(account.account_id, account.user_id):
                result["cooldown_active"] = True
                remaining_time = self.cooldown_service.get_remaining_time(account.account_id, account.user_id)
                cooldown = self.cooldown_service.get_active_cooldown(account.account_id, account.user_id)
                if cooldown:
                    result["cooldown_expires"] = cooldown.expires_at
                
                # If in cooldown, we can still get balances to show sync percentage
                self._add_balance_data(account, result)
            else:
                # Not in cooldown, analyze for potential actions
                self._add_balance_data(account, result)
                
                # Determine if pot needs updating
                if result["card_balance"] is not None and result["pot_balance"] is not None:
                    diff = result["card_balance"] - result["pot_balance"]
                    
                    if abs(diff) >= 100:  # Difference of at least £1
                        result["pot_needs_update"] = True
                        result["update_amount"] = diff
                        result["action_type"] = "deposit" if diff > 0 else "withdraw"
                    
                    # Calculate sync percentage
                    if result["card_balance"] != 0:
                        sync_level = max(0, 100 - min(100, (100 * abs(diff) / abs(result["card_balance"]))))
                        result["sync_percentage"] = round(sync_level)
                    else:
                        # If card balance is 0, calculate based on pot balance
                        if result["pot_balance"] == 0:
                            result["sync_percentage"] = 100  # Both zero means perfect sync
                        else:
                            result["sync_percentage"] = 0  # Card is 0 but pot isn't
            
            results.append(result)
        
        return results
    
    def _add_balance_data(self, account, result):
        """Add balance data to the result.
        
        Args:
            account: Account object
            result: Result dictionary to update
        """
        try:
            # Get card balance
            if self.balance_service:
                card_balance = self.balance_service.get_credit_card_balance(account)
                result["card_balance"] = card_balance
                
                # Get pot balance
                pot_balance = self.balance_service.get_pot_balance(account)
                result["pot_balance"] = pot_balance
                
                # If either balance is unavailable, set error
                if card_balance is None or pot_balance is None:
                    result["error"] = "Could not retrieve one or both balances"
        except Exception as e:
            log.error(f"Error getting balances for account {account.id}: {str(e)}")
            result["error"] = f"Error retrieving balances: {str(e)}"
    
    def filter_accounts(self, accounts, filters=None) -> List:
        """Filter accounts based on criteria.
        
        Args:
            accounts: List of account objects
            filters: Dictionary of filter criteria
            
        Returns:
            list: Filtered accounts
        """
        if not filters:
            return accounts
        
        filtered = accounts
        
        # Filter by type
        if "type" in filters:
            filtered = [a for a in filtered if a.type == filters["type"]]
        
        # Filter by user_id
        if "user_id" in filters:
            filtered = [a for a in filtered if a.user_id == filters["user_id"]]
        
        # Filter by cooldown status
        if "in_cooldown" in filters and self.cooldown_service:
            in_cooldown = filters["in_cooldown"]
            filtered = [
                a for a in filtered if 
                self.cooldown_service.is_in_cooldown(a.account_id, a.user_id) == in_cooldown
            ]
        
        # Filter by pot_id presence
        if "has_pot" in filters:
            has_pot = filters["has_pot"]
            filtered = [a for a in filtered if bool(a.pot_id) == has_pot]
        
        return filtered
    
    def get_accounts_needing_action(self) -> List:
        """Get accounts that need action (not in cooldown and with pot mappings).
        
        Returns:
            list: Accounts needing potential action
        """
        if not self.account_service or not self.cooldown_service:
            log.error("Required services not available")
            return []
        
        try:
            # Get all accounts
            all_accounts = self.account_service.get_all_accounts()
            
            # Filter accounts
            return self.filter_accounts(all_accounts, {
                "in_cooldown": False,
                "has_pot": True
            })
        except Exception as e:
            log.error(f"Error getting accounts needing action: {str(e)}")
            return []
