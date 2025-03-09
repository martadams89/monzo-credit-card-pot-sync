"""Service for interacting with Monzo API."""

import logging
import time
from urllib import parse
import requests
from app.errors import AuthException
from app.utils.error_handler import handle_error, ServiceError

logger = logging.getLogger(__name__)

class MonzoService:
    """Service for interacting with Monzo API."""
    
    def __init__(self, setting_repository, account_repository):
        """Initialize the service with repositories."""
        self.setting_repository = setting_repository
        self.account_repository = account_repository
        self.api_url = "https://api.monzo.com"
    
    def get_auth_header(self, account):
        """Get authentication header for API requests."""
        return {"Authorization": f"Bearer {account.access_token}"}
    
    def refresh_token(self, account):
        """Refresh the account's access token if needed."""
        try:
            current_time = int(time.time())
            if account.token_expiry and account.token_expiry <= current_time + 120:
                client_id = self.setting_repository.get('monzo_client_id')
                client_secret = self.setting_repository.get('monzo_client_secret')
                
                data = {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": account.refresh_token
                }
                
                response = requests.post("https://api.monzo.com/oauth2/token", data=data)
                response.raise_for_status()
                
                tokens = response.json()
                account.access_token = tokens["access_token"]
                account.refresh_token = tokens["refresh_token"]
                account.token_expiry = int(time.time()) + tokens["expires_in"]
                
                # Save updated tokens
                self.account_repository.save(account)
                return True
        except Exception as e:
            logger.error(f"Error refreshing Monzo token: {str(e)}")
            raise AuthException("Failed to refresh Monzo token", details={"error": str(e)})
        return False
    
    def ping(self, account):
        """Ping the API to verify the connection."""
        try:
            self.refresh_token(account)
            response = requests.get(f"{self.api_url}/ping/whoami", headers=self.get_auth_header(account))
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error pinging Monzo API: {str(e)}")
            raise AuthException("Failed to connect to Monzo API", details={"error": str(e)})
    
    def get_accounts(self, account):
        """Get list of accounts from Monzo."""
        try:
            self.refresh_token(account)
            response = requests.get(f"{self.api_url}/accounts", headers=self.get_auth_header(account))
            response.raise_for_status()
            return response.json()["accounts"]
        except Exception as e:
            logger.error(f"Error getting Monzo accounts: {str(e)}")
            raise ServiceError(f"Failed to get Monzo accounts: {str(e)}")
    
    def get_account_id(self, account, account_selection="personal"):
        """Get account ID based on type selection."""
        # Treat any account selection not 'joint' as 'personal'
        if account_selection != "joint":
            account_selection = "personal"
            
        desired_type = "uk_retail_joint" if account_selection == "joint" else "uk_retail"
        accounts = self.get_accounts(account)
        
        for acct in accounts:
            if acct["type"] == desired_type:
                return acct["id"]
                
        raise ServiceError(f"No Monzo account found for type: {desired_type}")
    
    def get_balance(self, account, account_selection="personal"):
        """Get account balance."""
        try:
            self.refresh_token(account)
            account_id = self.get_account_id(account, account_selection)
            query = parse.urlencode({"account_id": account_id})
            
            response = requests.get(
                f"{self.api_url}/balance?{query}",
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            
            return response.json()["balance"]
        except Exception as e:
            logger.error(f"Error getting Monzo balance: {str(e)}")
            raise ServiceError(f"Failed to get Monzo balance: {str(e)}")
    
    def get_pots(self, account, account_selection="personal"):
        """Get pots for the account."""
        try:
            self.refresh_token(account)
            current_account_id = self.get_account_id(account, account_selection)
            query = parse.urlencode({"current_account_id": current_account_id})
            
            response = requests.get(
                f"{self.api_url}/pots?{query}",
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            
            pots = response.json()["pots"]
            return [p for p in pots if not p["deleted"]]
        except Exception as e:
            logger.error(f"Error getting Monzo pots: {str(e)}")
            raise ServiceError(f"Failed to get Monzo pots: {str(e)}")
    
    def get_pot_balance(self, account, pot_id):
        """Get pot balance."""
        try:
            # Try personal account first, then joint if needed
            for account_selection in ["personal", "joint"]:
                try:
                    pots = self.get_pots(account, account_selection)
                    pot = next((p for p in pots if p["id"] == pot_id), None)
                    if pot:
                        return pot["balance"]
                except:
                    continue
                    
            raise ServiceError(f"Pot with ID {pot_id} not found")
        except Exception as e:
            logger.error(f"Error getting pot balance: {str(e)}")
            raise ServiceError(f"Failed to get pot balance: {str(e)}")
    
    def update_pot(self, account, pot_id, target_amount):
        """Update pot to match target amount (deposit or withdraw as needed)."""
        try:
            # Check if we need to deposit or withdraw
            current_balance = self.get_pot_balance(account, pot_id)
            account_selection = self.get_account_type(account, pot_id)
            
            if target_amount > current_balance:
                # Need to deposit
                amount = target_amount - current_balance
                self.add_to_pot(account, pot_id, amount, account_selection)
                return True
            elif target_amount < current_balance:
                # Need to withdraw
                amount = current_balance - target_amount
                self.withdraw_from_pot(account, pot_id, amount, account_selection)
                return True
                
            return False # No change needed
        except Exception as e:
            logger.error(f"Error updating pot: {str(e)}")
            raise ServiceError(f"Failed to update pot: {str(e)}")
    
    def get_account_type(self, account, pot_id):
        """Determine if pot belongs to personal or joint account."""
        for account_selection in ["personal", "joint"]:
            try:
                pots = self.get_pots(account, account_selection)
                if any(p["id"] == pot_id for p in pots):
                    return account_selection
            except:
                continue
                
        raise ServiceError(f"Pot with ID {pot_id} not found in any account")
    
    def add_to_pot(self, account, pot_id, amount, account_selection="personal"):
        """Add money to a pot."""
        try:
            self.refresh_token(account)
            
            # Verify pot exists in selected account
            pots = self.get_pots(account, account_selection)
            pot = next((p for p in pots if p["id"] == pot_id), None)
            if not pot:
                raise ServiceError(f"Pot with ID {pot_id} not found in {account_selection} account")
            
            data = {
                "source_account_id": self.get_account_id(account, account_selection),
                "amount": amount,
                "dedupe_id": str(int(time.time()))
            }
            
            response = requests.put(
                f"{self.api_url}/pots/{pot_id}/deposit",
                data=data,
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error adding to pot: {str(e)}")
            raise ServiceError(f"Failed to add to pot: {str(e)}")
    
    def withdraw_from_pot(self, account, pot_id, amount, account_selection="personal"):
        """Withdraw money from a pot."""
        try:
            self.refresh_token(account)
            
            # Verify pot exists in selected account
            pots = self.get_pots(account, account_selection)
            pot = next((p for p in pots if p["id"] == pot_id), None)
            if not pot:
                raise ServiceError(f"Pot with ID {pot_id} not found in {account_selection} account")
            
            data = {
                "destination_account_id": self.get_account_id(account, account_selection),
                "amount": amount,
                "dedupe_id": str(int(time.time()))
            }
            
            response = requests.put(
                f"{self.api_url}/pots/{pot_id}/withdraw",
                data=data,
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error withdrawing from pot: {str(e)}")
            raise ServiceError(f"Failed to withdraw from pot: {str(e)}")
    
    def send_notification(self, account, title, message, account_selection="personal"):
        """Send a notification to the account."""
        try:
            self.refresh_token(account)
            
            body = {
                "account_id": self.get_account_id(account, account_selection),
                "type": "basic",
                "params[image_url]": "https://www.nyan.cat/cats/original.gif",
                "params[title]": title,
                "params[body]": message
            }
            
            response = requests.post(
                f"{self.api_url}/feed",
                data=body,
                headers=self.get_auth_header(account)
            )
            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return False  # Non-critical, so just return False instead of raising exception
