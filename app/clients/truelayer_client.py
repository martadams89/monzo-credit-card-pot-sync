"""Client for interacting with TrueLayer API."""

import logging
import requests
from typing import Dict, Any, Optional, List

log = logging.getLogger("truelayer_client")

class TrueLayerClient:
    """Client for interacting with the TrueLayer API."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize TrueLayerClient.
        
        Args:
            client_id: TrueLayer OAuth client ID
            client_secret: TrueLayer OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.truelayer.com"
        self.auth_url = "https://auth.truelayer.com"
    
    def get_authorization_url(self, state: str, provider: Optional[str] = None,
                             scopes: Optional[List[str]] = None) -> str:
        """Get the authorization URL for OAuth flow.
        
        Args:
            state: State parameter for OAuth security
            provider: Optional provider ID
            scopes: Optional list of scopes
            
        Returns:
            str: The authorization URL
        """
        if scopes is None:
            scopes = ["info", "accounts", "balance", "cards"]
            
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state
        }
        
        if provider:
            params["providers"] = provider
            
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
            
            response = requests.post(f"{self.auth_url}/connect/token", data=payload, timeout=10)
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
            
            response = requests.post(f"{self.auth_url}/connect/token", data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error refreshing token: {str(e)}")
            return None
    
    def get_cards(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get all cards for a user.
        
        Args:
            access_token: User's access token
            
        Returns:
            dict: Cards data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.base_url}/data/v1/cards", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error getting cards: {str(e)}")
            return None
    
    def get_card_balance(self, access_token: str, card_id: str = "") -> Optional[Dict[str, Any]]:
        """Get balance for a card.
        
        Args:
            access_token: User's access token
            card_id: Card ID (optional)
            
        Returns:
            dict: Balance data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            url = f"{self.base_url}/data/v1/cards/{card_id}/balance" if card_id else f"{self.base_url}/data/v1/cards/balance"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract balance information from the response
            # Format might differ between providers, handle the most common formats
            if 'results' in data and data['results']:
                return data['results'][0]
            elif 'balance' in data:
                return data['balance']
                
            log.error("Unexpected balance format")
            return None
            
        except requests.RequestException as e:
            log.error(f"Error getting card balance: {str(e)}")
            return None
    
    def get_accounts(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get all bank accounts for a user.
        
        Args:
            access_token: User's access token
            
        Returns:
            dict: Accounts data or None if failed
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.base_url}/data/v1/accounts", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            log.error(f"Error getting accounts: {str(e)}")
            return None
