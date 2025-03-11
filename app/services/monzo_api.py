import logging
import time
import requests
from typing import Dict, List, Optional, Union, Any
from requests.exceptions import RequestException
from functools import wraps
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

def retry_on_error(max_retries=3, backoff_factor=0.5):
    """Decorator for retrying API calls on failure with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (RequestException, MonzoAPIError) as e:
                    retries += 1
                    if retries >= max_retries:
                        log.error(f"Max retries ({max_retries}) reached for {func.__name__}. Error: {str(e)}")
                        raise
                    
                    wait_time = backoff_factor * (2 ** (retries - 1))
                    log.warning(f"API call to {func.__name__} failed. Retrying in {wait_time}s. Error: {str(e)}")
                    time.sleep(wait_time)
        return wrapper
    return decorator

class MonzoAPIError(Exception):
    """Custom exception for Monzo API errors."""
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class MonzoAPI:
    """Client for interacting with the Monzo API."""
    
    BASE_URL = "https://api.monzo.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make a request to the Monzo API with error handling."""
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                data=data
            )
            
            # Check for error responses
            if not response.ok:
                error_msg = f"Monzo API error: {response.status_code}"
                try:
                    error_json = response.json()
                    if 'message' in error_json:
                        error_msg = f"Monzo API error: {error_json['message']}"
                except ValueError:
                    pass
                
                raise MonzoAPIError(error_msg, status_code=response.status_code, response=response)
            
            return response.json()
            
        except RequestException as e:
            log.error(f"Request error: {str(e)}")
            raise MonzoAPIError(f"Request failed: {str(e)}")
    
    @retry_on_error()
    def get_accounts(self) -> List[Dict]:
        """Get a list of accounts."""
        response = self._make_request("GET", "/accounts")
        return response.get("accounts", [])
    
    @retry_on_error()
    def get_balance(self, account_id: str) -> Dict:
        """Get the balance for an account."""
        response = self._make_request("GET", f"/balance", params={"account_id": account_id})
        return response
    
    @retry_on_error()
    def get_pots(self, account_id: str = None) -> List[Dict]:
        """Get a list of pots."""
        response = self._make_request("GET", "/pots")
        pots = response.get("pots", [])
        
        # Filter by account_id if provided
        if account_id:
            pots = [pot for pot in pots if pot.get("current_account_id") == account_id]
        
        return pots
    
    @retry_on_error()
    def deposit_to_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: str) -> Dict:
        """Deposit money into a pot."""
        data = {
            "source_account_id": account_id,
            "amount": amount,
            "dedupe_id": dedupe_id
        }
        response = self._make_request("PUT", f"/pots/{pot_id}/deposit", data=data)
        return response
    
    @retry_on_error()
    def withdraw_from_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: str) -> Dict:
        """Withdraw money from a pot."""
        data = {
            "destination_account_id": account_id,
            "amount": amount,
            "dedupe_id": dedupe_id
        }
        response = self._make_request("PUT", f"/pots/{pot_id}/withdraw", data=data)
        return response
    
    @retry_on_error()
    def get_transactions(
        self, 
        account_id: str, 
        since: Optional[datetime] = None, 
        before: Optional[datetime] = None, 
        limit: int = 100
    ) -> List[Dict]:
        """Get transactions for an account."""
        params = {
            "account_id": account_id,
            "limit": limit,
            "expand[]": "merchant"
        }
        
        if since:
            params["since"] = since.isoformat() + "Z"
        if before:
            params["before"] = before.isoformat() + "Z"
        
        response = self._make_request("GET", "/transactions", params=params)
        return response.get("transactions", [])
    
    @retry_on_error()
    def get_transaction(self, transaction_id: str, expand_merchant: bool = True) -> Dict:
        """Get details of a specific transaction."""
        params = {}
        if expand_merchant:
            params["expand[]"] = "merchant"
        
        response = self._make_request("GET", f"/transactions/{transaction_id}", params=params)
        return response.get("transaction", {})
    
    @retry_on_error()
    def create_feed_item(self, 
                         account_id: str, 
                         title: str, 
                         image_url: str, 
                         body: str,
                         background_color: str = "#FCF1EE"
                        ) -> Dict:
        """Create a feed item in the Monzo app."""
        data = {
            "account_id": account_id,
            "type": "basic",
            "params[title]": title,
            "params[image_url]": image_url,
            "params[body]": body,
            "params[background_color]": background_color
        }
        
        response = self._make_request("POST", "/feed", data=data)
        return response
    
    @retry_on_error()
    def register_webhook(self, account_id: str, url: str) -> Dict:
        """Register a webhook for account events."""
        data = {
            "account_id": account_id,
            "url": url
        }
        
        response = self._make_request("POST", "/webhooks", data=data)
        return response
    
    @retry_on_error()
    def list_webhooks(self, account_id: str) -> List[Dict]:
        """List all registered webhooks for an account."""
        params = {"account_id": account_id}
        
        response = self._make_request("GET", "/webhooks", params=params)
        return response.get("webhooks", [])
    
    @retry_on_error()
    def delete_webhook(self, webhook_id: str) -> Dict:
        """Delete a webhook."""
        response = self._make_request("DELETE", f"/webhooks/{webhook_id}")
        return response
    
    def is_valid_token(self) -> bool:
        """Check if the token is valid by making a simple API call."""
        try:
            self.get_accounts()
            return True
        except MonzoAPIError:
            return False

import logging
import requests
import time
import uuid
from typing import Dict, List, Optional, Any
from flask import current_app
from urllib.parse import urlencode
from datetime import datetime

from app.models.monzo import MonzoAccount
from app.errors import AuthException

log = logging.getLogger(__name__)

class MonzoAPIService:
    """Service for interacting with the Monzo API."""
    
    def __init__(self):
        # Removed immediate retrieval of configuration to avoid application context errors.
        self.api_base_url = "https://api.monzo.com"
        self.auth_url = "https://auth.monzo.com"
        # ...other initialization...
    
    @property
    def client_id(self):
        from flask import current_app
        return current_app.config.get('MONZO_CLIENT_ID')
    
    @property
    def client_secret(self):
        from flask import current_app
        return current_app.config.get('MONZO_CLIENT_SECRET')
    
    @property
    def redirect_uri(self):
        from flask import current_app
        return current_app.config.get('MONZO_REDIRECT_URI')
    
    def get_auth_url(self, state: str) -> str:
        """Get the authorization URL for the OAuth flow."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'state': state
        }
        return f"{self.auth_url}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange the authorization code for access and refresh tokens."""
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': code
        }
        
        response = requests.post(f"{self.api_base_url}/oauth2/token", data=data)
        
        if response.status_code != 200:
            log.error(f"Error exchanging code for tokens: {response.text}")
            raise AuthException("Failed to exchange authorization code for tokens")
        
        return response.json()
    
    def refresh_access_token(self, account: MonzoAccount) -> Dict[str, Any]:
        """Refresh the access token for a Monzo account."""
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': account.refresh_token
        }
        
        response = requests.post(f"{self.api_base_url}/oauth2/token", data=data)
        
        if response.status_code != 200:
            log.error(f"Error refreshing token: {response.text}")
            raise AuthException("Failed to refresh access token")
        
        result = response.json()
        
        # Update the account with new tokens
        account.access_token = result['access_token']
        account.refresh_token = result['refresh_token']
        account.token_expires_at = int(time.time()) + result['expires_in']
        
        return result
    
    def _ensure_valid_token(self, account: MonzoAccount) -> None:
        """Ensure the account has a valid token, refreshing if necessary."""
        current_time = int(time.time())
        
        # Check if token is expired or about to expire (within 60 seconds)
        if account.token_expires_at - current_time <= 60:
            log.info(f"Access token for account {account.id} is about to expire, refreshing")
            self.refresh_access_token(account)
    
    def get_accounts(self, monzo_account: MonzoAccount) -> List[Dict[str, Any]]:
        """Get all accounts for the user."""
        self._ensure_valid_token(monzo_account)
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        response = requests.get(f"{self.api_base_url}/accounts", headers=headers)
        
        if response.status_code != 200:
            log.error(f"Error fetching accounts: {response.text}")
            raise Exception("Failed to fetch Monzo accounts")
        
        return response.json()['accounts']
    
    def get_account_details(self, monzo_account: MonzoAccount) -> Dict[str, Any]:
        """Get details for the first UK retail account."""
        accounts = self.get_accounts(monzo_account)
        
        # Filter for UK retail accounts
        uk_accounts = [acc for acc in accounts if acc.get('type') == 'uk_retail']
        
        if not uk_accounts:
            log.warning("No UK retail accounts found")
            return {}
        
        # Return the first UK retail account
        return uk_accounts[0]
    
    def get_balance(self, monzo_account: MonzoAccount) -> Dict[str, Any]:
        """Get balance for the account."""
        self._ensure_valid_token(monzo_account)
        
        if not monzo_account.account_id:
            account_details = self.get_account_details(monzo_account)
            if not account_details:
                log.error("No account ID available to fetch balance")
                return {}
            monzo_account.account_id = account_details['id']
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        params = {'account_id': monzo_account.account_id}
        response = requests.get(f"{self.api_base_url}/balance", headers=headers, params=params)
        
        if response.status_code != 200:
            log.error(f"Error fetching balance: {response.text}")
            raise Exception("Failed to fetch balance")
        
        return response.json()
    
    def get_pots(self, monzo_account: MonzoAccount) -> List[Dict[str, Any]]:
        """Get all pots for the account."""
        self._ensure_valid_token(monzo_account)
        
        if not monzo_account.account_id:
            account_details = self.get_account_details(monzo_account)
            if not account_details:
                log.error("No account ID available to fetch pots")
                return []
            monzo_account.account_id = account_details['id']
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        params = {'current_account_id': monzo_account.account_id}
        response = requests.get(f"{self.api_base_url}/pots", headers=headers, params=params)
        
        if response.status_code != 200:
            log.error(f"Error fetching pots: {response.text}")
            raise Exception("Failed to fetch pots")
        
        # Filter out deleted pots
        pots = response.json()['pots']
        return [pot for pot in pots if not pot.get('deleted', False)]
    
    def deposit_to_pot(self, monzo_account: MonzoAccount, pot_id: str, amount: int) -> bool:
        """Deposit money to a pot."""
        self._ensure_valid_token(monzo_account)
        
        if not monzo_account.account_id:
            account_details = self.get_account_details(monzo_account)
            if not account_details:
                log.error("No account ID available for deposit")
                return False
            monzo_account.account_id = account_details['id']
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        data = {
            'source_account_id': monzo_account.account_id,
            'amount': amount,
            'dedupe_id': str(uuid.uuid4())
        }
        
        response = requests.put(f"{self.api_base_url}/pots/{pot_id}/deposit", headers=headers, data=data)
        
        if response.status_code != 200:
            log.error(f"Error depositing to pot: {response.text}")
            return False
        
        return True
    
    def withdraw_from_pot(self, monzo_account: MonzoAccount, pot_id: str, amount: int) -> bool:
        """Withdraw money from a pot."""
        self._ensure_valid_token(monzo_account)
        
        if not monzo_account.account_id:
            account_details = self.get_account_details(monzo_account)
            if not account_details:
                log.error("No account ID available for withdrawal")
                return False
            monzo_account.account_id = account_details['id']
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        data = {
            'destination_account_id': monzo_account.account_id,
            'amount': amount,
            'dedupe_id': str(uuid.uuid4())
        }
        
        response = requests.put(f"{self.api_base_url}/pots/{pot_id}/withdraw", headers=headers, data=data)
        
        if response.status_code != 200:
            log.error(f"Error withdrawing from pot: {response.text}")
            return False
        
        return True
    
    def get_transactions(self, monzo_account: MonzoAccount, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transactions for the account."""
        self._ensure_valid_token(monzo_account)
        
        if not monzo_account.account_id:
            account_details = self.get_account_details(monzo_account)
            if not account_details:
                log.error("No account ID available to fetch transactions")
                return []
            monzo_account.account_id = account_details['id']
        
        headers = {'Authorization': f'Bearer {monzo_account.access_token}'}
        params = {
            'account_id': monzo_account.account_id,
            'limit': limit
        }
        response = requests.get(f"{self.api_base_url}/transactions", headers=headers, params=params)
        
        if response.status_code != 200:
            log.error(f"Error fetching transactions: {response.text}")
            raise Exception("Failed to fetch transactions")
        
        return response.json()['transactions']
    
    def send_feed_item(self, account_id: str, title: str, body: str, access_token: str = None,
                        image_url: str = None, background_color: str = "#FCF1EE") -> bool:
        """Create a feed item (notification) in the Monzo app."""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            data = {
                'account_id': account_id,
                'type': 'basic',
                'params[title]': title,
                'params[body]': body,
                'params[background_color]': background_color
            }
            
            if image_url:
                data['params[image_url]'] = image_url
            
            response = requests.post(f"{self.api_base_url}/feed", headers=headers, data=data)
            
            return response.status_code == 200
        except Exception as e:
            log.error(f"Error sending feed item: {str(e)}")
            return False
