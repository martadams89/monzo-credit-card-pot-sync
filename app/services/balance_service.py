"""Service for retrieving and managing balance information."""

import logging
import time
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)

class BalanceService:
    """Service for retrieving and managing balance information."""
    
    def __init__(self, monzo_client=None, truelayer_client=None, setting_repository=None):
        """Initialize BalanceService.
        
        Args:
            monzo_client: Client for Monzo API
            truelayer_client: Client for TrueLayer API
            setting_repository: Repository for settings
        """
        self.monzo_client = monzo_client
        self.truelayer_client = truelayer_client
        self.setting_repository = setting_repository
    
    def get_credit_card_balance(self, account) -> Optional[int]:
        """Get the balance for a credit card account.
        
        Args:
            account: Account model
            
        Returns:
            int: Balance in pence/cents, or None if failed
        """
        try:
            # Ensure token is still valid
            self._refresh_token_if_needed(account)
            
            # Determine which client to use based on account type
            if account.type.lower() == "monzo":
                log.error("Cannot get credit card balance for Monzo account")
                return None
                
            # For TrueLayer-based providers
            if self.truelayer_client:
                response = self.truelayer_client.get_card_balance(account.access_token)
                
                if not response:
                    log.error(f"Failed to get balance for {account.type}")
                    return None
                
                # Extract the current balance from response
                # Format might vary between credit card providers
                if 'current' in response:
                    # For standard TrueLayer response
                    balance = response['current']
                elif 'balance' in response and 'amount' in response['balance']:
                    # Alternative format
                    balance = response['balance']['amount']
                else:
                    log.error(f"Unexpected balance response format for {account.type}")
                    return None
                
                # Convert to pence/cents as integer
                # Credit card balances are typically positive when money is owed
                # But we want to represent money owed as a negative number for our app logic
                balance_pence = int(float(balance) * -100)
                
                log.info(f"{account.type} balance: {balance_pence/100:.2f}")
                return balance_pence
            else:
                log.error("No TrueLayer client available")
                return None
                
        except Exception as e:
            log.error(f"Error getting credit card balance: {str(e)}", exc_info=True)
            return None
    
    def get_pot_balance(self, account) -> Optional[int]:
        """Get the balance for a Monzo pot.
        
        Args:
            account: Account model with pot_id field
            
        Returns:
            int: Pot balance in pence/cents, or None if failed
        """
        try:
            # For Monzo accounts, we need the Monzo user's access token
            monzo_account = self._get_monzo_account(account.user_id)
            if not monzo_account:
                log.error("No Monzo account available")
                return None
                
            # Ensure token is still valid
            self._refresh_token_if_needed(monzo_account)
            
            # Get pot details
            if self.monzo_client and monzo_account.access_token and account.pot_id:
                response = self.monzo_client.get_pots(monzo_account.access_token)
                
                if not response or 'pots' not in response:
                    log.error("Failed to get pots")
                    return None
                
                # Find the specific pot
                for pot in response['pots']:
                    if pot['id'] == account.pot_id:
                        balance = pot['balance']
                        log.info(f"Pot balance: {balance/100:.2f}")
                        return balance
                
                log.error(f"Pot {account.pot_id} not found")
                return None
            else:
                log.error("Missing required data for getting pot balance")
                return None
                
        except Exception as e:
            log.error(f"Error getting pot balance: {str(e)}", exc_info=True)
            return None
    
    def deposit_to_pot(self, account, amount, dedupe_id) -> Dict[str, Any]:
        """Deposit money into a pot.
        
        Args:
            account: Account model with pot_id field
            amount: Amount to deposit in pence/cents
            dedupe_id: Unique ID to prevent duplicate operations
            
        Returns:
            dict: Result of the operation
        """
        try:
            # For Monzo accounts, we need the Monzo user's access token
            monzo_account = self._get_monzo_account(account.user_id)
            if not monzo_account:
                return {"success": False, "message": "No Monzo account available"}
                
            # Ensure token is still valid
            self._refresh_token_if_needed(monzo_account)
            
            # Deposit to pot
            if self.monzo_client and monzo_account.access_token and account.pot_id:
                # Get Monzo account ID - we need this as the source account
                accounts_response = self.monzo_client.get_accounts(monzo_account.access_token)
                if not accounts_response or 'accounts' not in accounts_response:
                    return {"success": False, "message": "Failed to get Monzo accounts"}
                
                # Find the main account (usually there's only one, but just in case)
                monzo_account_id = None
                for acc in accounts_response['accounts']:
                    if acc['closed'] is False:
                        monzo_account_id = acc['id']
                        break
                
                if not monzo_account_id:
                    return {"success": False, "message": "No active Monzo account found"}
                
                # Execute deposit
                deposit_response = self.monzo_client.deposit_to_pot(
                    monzo_account.access_token,
                    account.pot_id,
                    monzo_account_id,
                    amount,
                    dedupe_id
                )
                
                if deposit_response:
                    return {
                        "success": True,
                        "message": f"Deposited {amount/100:.2f}",
                        "start_cooldown": True
                    }
                else:
                    return {"success": False, "message": "Deposit to pot failed"}
            else:
                return {"success": False, "message": "Missing required data for deposit"}
                
        except Exception as e:
            log.error(f"Error depositing to pot: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def withdraw_from_pot(self, account, amount, dedupe_id) -> Dict[str, Any]:
        """Withdraw money from a pot.
        
        Args:
            account: Account model with pot_id field
            amount: Amount to withdraw in pence/cents
            dedupe_id: Unique ID to prevent duplicate operations
            
        Returns:
            dict: Result of the operation
        """
        try:
            # For Monzo accounts, we need the Monzo user's access token
            monzo_account = self._get_monzo_account(account.user_id)
            if not monzo_account:
                return {"success": False, "message": "No Monzo account available"}
                
            # Ensure token is still valid
            self._refresh_token_if_needed(monzo_account)
            
            # Withdraw from pot
            if self.monzo_client and monzo_account.access_token and account.pot_id:
                # Get Monzo account ID - we need this as the destination account
                accounts_response = self.monzo_client.get_accounts(monzo_account.access_token)
                if not accounts_response or 'accounts' not in accounts_response:
                    return {"success": False, "message": "Failed to get Monzo accounts"}
                
                # Find the main account (usually there's only one, but just in case)
                monzo_account_id = None
                for acc in accounts_response['accounts']:
                    if acc['closed'] is False:
                        monzo_account_id = acc['id']
                        break
                
                if not monzo_account_id:
                    return {"success": False, "message": "No active Monzo account found"}
                
                # Execute withdrawal
                withdraw_response = self.monzo_client.withdraw_from_pot(
                    monzo_account.access_token,
                    account.pot_id,
                    monzo_account_id,
                    amount,
                    dedupe_id
                )
                
                if withdraw_response:
                    return {
                        "success": True,
                        "message": f"Withdrew {amount/100:.2f}",
                        "start_cooldown": True
                    }
                else:
                    return {"success": False, "message": "Withdrawal from pot failed"}
            else:
                return {"success": False, "message": "Missing required data for withdrawal"}
                
        except Exception as e:
            log.error(f"Error withdrawing from pot: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _get_monzo_account(self, user_id):
        """Get the user's Monzo account.
        
        Args:
            user_id: User ID
            
        Returns:
            Account: Monzo account or None
        """
        from app.services.account_service import AccountService
        account_service = AccountService()
        return account_service.get_user_monzo_account(user_id)
    
    def _refresh_token_if_needed(self, account) -> bool:
        """Refresh access token if it's expired or about to expire.
        
        Args:
            account: Account model
            
        Returns:
            bool: True if token is valid (refreshed or not), False otherwise
        """
        # Check if token is about to expire (within 5 minutes)
        current_time = int(time.time())
        if not account.token_expiry or account.token_expiry - current_time < 300:
            from app.services.account_service import AccountService
            account_service = AccountService()
            return account_service.refresh_token(account)
            
        return True
