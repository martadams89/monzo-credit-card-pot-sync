"""Service for interacting with TrueLayer (credit card) APIs."""

import logging
import time
import math
import requests
from app.errors import AuthException
from app.utils.error_handler import handle_error, ServiceError

logger = logging.getLogger(__name__)

class TrueLayerService:
    """Service for interacting with credit card APIs via TrueLayer."""
    
    def __init__(self, setting_repository, account_repository):
        """Initialize the service with repositories."""
        self.setting_repository = setting_repository
        self.account_repository = account_repository
        self.api_url = "https://api.truelayer.com"
    
    def get_auth_header(self, account):
        """Get authentication header for API requests."""
        return {"Authorization": f"Bearer {account.access_token}"}
    
    def refresh_token(self, account):
        """Refresh the account's access token if needed."""
        try:
            current_time = int(time.time())
            if account.token_expiry and account.token_expiry <= current_time + 120:
                client_id = self.setting_repository.get('truelayer_client_id')
                client_secret = self.setting_repository.get('truelayer_client_secret')
                
                data = {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": account.refresh_token
                }
                
                response = requests.post("https://auth.truelayer.com/connect/token", data=data)
                response.raise_for_status()
                
                tokens = response.json()
                account.access_token = tokens["access_token"]
                account.refresh_token = tokens["refresh_token"]
                account.token_expiry = int(time.time()) + tokens["expires_in"]
                
                # Save updated tokens
                self.account_repository.save(account)
                return True
        except Exception as e:
            logger.error(f"Error refreshing credit card token: {str(e)}")
            raise AuthException("Failed to refresh credit card token", details={"error": str(e)})
        return False
    
    def ping(self, account):
        """Ping the API to verify the connection."""
        try:
            self.refresh_token(account)
            response = requests.get(f"{self.api_url}/data/v1/me", headers=self.get_auth_header(account))
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error pinging credit card API: {str(e)}")
            raise AuthException("Failed to connect to credit card API", details={"error": str(e)})
    
    def get_cards(self, account):
        """Get list of credit cards."""
        try:
            self.refresh_token(account)
            response = requests.get(f"{self.api_url}/data/v1/cards", headers=self.get_auth_header(account))
            response.raise_for_status()
            return response.json()["results"]
        except Exception as e:
            logger.error(f"Error getting credit cards: {str(e)}")
            raise ServiceError(f"Failed to get credit cards: {str(e)}")
    
    def get_card_balance(self, account, card_id):
        """Get balance for specific card."""
        try:
            self.refresh_token(account)
            response = requests.get(
                f"{self.api_url}/data/v1/cards/{card_id}/balance",
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            data = response.json()["results"][0]
            
            # Calculate accurate balance amount
            return math.ceil(data["current"] * 100) / 100
        except Exception as e:
            logger.error(f"Error getting card balance: {str(e)}")
            raise ServiceError(f"Failed to get card balance: {str(e)}")
    
    def get_pending_transactions(self, account, card_id):
        """Get pending transactions for a card."""
        try:
            self.refresh_token(account)
            response = requests.get(
                f"{self.api_url}/data/v1/cards/{card_id}/transactions/pending",
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            transactions = response.json()["results"]
            
            # Process transaction amounts
            return [math.ceil(txn["amount"] * 100) / 100 for txn in transactions] if transactions else []
        except Exception as e:
            logger.error(f"Error getting pending transactions: {str(e)}")
            raise ServiceError(f"Failed to get pending transactions: {str(e)}")
    
    def get_total_balance(self, account, force_refresh=False):
        """Calculate total balance across all cards including pending transactions."""
        try:
            # Use cached balance if available and not forcing refresh
            if not force_refresh and hasattr(account, '_cached_balance'):
                return account._cached_balance
                
            self.refresh_token(account)
            total_balance = 0.0
            cards = self.get_cards(account)
            
            for card in cards:
                card_id = card["account_id"]
                balance = self.get_card_balance(account, card_id)
                provider = card.get("provider", {}).get("display_name", "").upper()
                
                # Handle different credit card providers
                if provider in ["AMEX"]:
                    pending_transactions = self.get_pending_transactions(account, card_id)
                    pending_charges = math.ceil(sum(txn for txn in pending_transactions if txn > 0) * 100) / 100
                    pending_payments = math.ceil(sum(txn for txn in pending_transactions if txn < 0) * 100) / 100
                    pending_balance = pending_charges
                    adjusted_balance = balance + pending_balance
                    balance = adjusted_balance
                
                elif provider in ["BARCLAYCARD"]:
                    pending_transactions = self.get_pending_transactions(account, card_id)
                    pending_charges = math.ceil(sum(txn for txn in pending_transactions if txn > 0) * 100) / 100
                    pending_payments = math.ceil(sum(txn for txn in pending_transactions if txn < 0) * 100) / 100
                    net_pending = math.ceil(sum(pending_transactions) * 100) / 100
                    # Keep original balance for Barclaycard per original code
                
                total_balance += balance
            
            # Store the calculated balance in pence and cache it
            balance_in_pence = int(total_balance * 100)
            account._cached_balance = balance_in_pence
            
            # Update the account's balance in the database
            account.balance = balance_in_pence
            self.account_repository.save(account)
            
            return balance_in_pence
            
        except Exception as e:
            logger.error(f"Error calculating total balance: {str(e)}")
            raise ServiceError(f"Failed to calculate total balance: {str(e)}")
    
    def refresh_account(self, account):
        """Refresh account data, including balance."""
        try:
            from datetime import datetime  # Import here to avoid circular imports
            
            self.ping(account)
            balance = self.get_total_balance(account, force_refresh=True)
            
            # Update last refreshed timestamp
            account.updated_at = datetime.utcnow()
            self.account_repository.save(account)
            
            return True
        except Exception as e:
            logger.error(f"Error refreshing account: {str(e)}")
            return False
