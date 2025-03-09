"""Client for interacting with Monzo API."""

import logging
import requests
from typing import Dict, Any, Optional

log = logging.getLogger("monzo_client")

class MonzoClient:
    """Client for interacting with the Monzo API."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize MonzoClient.
        
        Args:
            client_id: Monzo OAuth client ID
            client_secret: Monzo OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.monzo.com"
        self.auth_url = "https://auth.monzo.com"
    
    def get_authorization_url(self, state: str) -> str:
        """Get the authorization URL for OAuth flow.
        
        Args:
            state: State parameter for OAuth security
            
        Returns:
            str: The authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state
        }
        
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}/?{query}"
    
    def exchange_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth flow
            
        Returns:
            dict: Token response or None if failed
        """
        try:
            payload = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code
            }
            
            response = requests.post(f"{self.base_url}/oauth2/token", data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error exchanging code: {str(e)}")
            return None
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh an access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            dict: New token response or None if failed
        """
        try:
            payload = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token
            }
            
            response = requests.post(f"{self.base_url}/oauth2/token", data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error refreshing token: {str(e)}")
            return None
    
    def get_accounts(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get all accounts for a user.
        
        Args:
            access_token: User's access token
            
        Returns:
            dict: Accounts data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.base_url}/accounts", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error getting accounts: {str(e)}")
            return None
    
    def get_balance(self, access_token: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get balance for an account.
        
        Args:
            access_token: User's access token
            account_id: Account ID
            
        Returns:
            dict: Balance data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.base_url}/balance", 
                                   params={"account_id": account_id},
                                   headers=headers,
                                   timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error getting balance: {str(e)}")
            return None
    
    def get_pots(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get all pots for a user.
        
        Args:
            access_token: User's access token
            
        Returns:
            dict: Pots data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.base_url}/pots", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error getting pots: {str(e)}")
            return None
    
    def deposit_to_pot(self, access_token: str, pot_id: str, account_id: str, 
                       amount: int, dedupe_id: str) -> Optional[Dict[str, Any]]:
        """Deposit money into a pot.
        
        Args:
            access_token: User's access token
            pot_id: ID of the pot
            account_id: Source account ID
            amount: Amount to deposit in pence
            dedupe_id: Unique ID to prevent duplicate transactions
            
        Returns:
            dict: Deposit response or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "source_account_id": account_id,
                "amount": amount,
                "dedupe_id": dedupe_id
            }
            
            response = requests.put(
                f"{self.base_url}/pots/{pot_id}/deposit",
                headers=headers,
                data=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error depositing to pot: {str(e)}")
            return None
    
    def withdraw_from_pot(self, access_token: str, pot_id: str, account_id: str,
                          amount: int, dedupe_id: str) -> Optional[Dict[str, Any]]:
        """Withdraw money from a pot.
        
        Args:
            access_token: User's access token
            pot_id: ID of the pot
            account_id: Destination account ID
            amount: Amount to withdraw in pence
            dedupe_id: Unique ID to prevent duplicate transactions
            
        Returns:
            dict: Withdrawal response or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            payload = {
                "destination_account_id": account_id,
                "amount": amount,
                "dedupe_id": dedupe_id
            }
            
            response = requests.put(
                f"{self.base_url}/pots/{pot_id}/withdraw",
                headers=headers,
                data=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error withdrawing from pot: {str(e)}")
            return None
