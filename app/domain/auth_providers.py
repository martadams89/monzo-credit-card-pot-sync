import os
import requests
import json
import logging
from enum import Enum
from typing import Dict, Any

log = logging.getLogger(__name__)

class AuthProviderType(Enum):
    MONZO = "monzo"
    BARCLAYS = "barclays"
    HSBC = "hsbc"
    SANTANDER = "santander"
    LLOYDS = "lloyds"
    NATWEST = "natwest"

class AuthProvider:
    """Base class for authentication providers."""
    
    def __init__(self, name: str, client_id: str, client_secret: str, redirect_uri: str):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def get_auth_url(self, state: str) -> str:
        """Get the authorization URL."""
        raise NotImplementedError("Subclasses must implement this")
    
    def handle_oauth_code_callback(self, code: str) -> Dict[str, Any]:
        """Handle the OAuth callback code and get tokens."""
        raise NotImplementedError("Subclasses must implement this")
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an access token using a refresh token."""
        raise NotImplementedError("Subclasses must implement this")

class MonzoAuthProvider(AuthProvider):
    """Authentication provider for Monzo."""
    
    def __init__(self):
        from flask import current_app
        
        super().__init__(
            name=AuthProviderType.MONZO.value,
            client_id=current_app.config.get('MONZO_CLIENT_ID'),
            client_secret=current_app.config.get('MONZO_CLIENT_SECRET'),
            redirect_uri=current_app.config.get('MONZO_REDIRECT_URI')
        )
        self.auth_url = "https://auth.monzo.com/"
        self.api_url = "https://api.monzo.com/"
    
    def get_auth_url(self, state: str) -> str:
        """Get the Monzo authorization URL."""
        return (
            f"{self.auth_url}?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&state={state}"
        )
    
    def handle_oauth_code_callback(self, code: str) -> Dict[str, Any]:
        """Handle the Monzo OAuth callback code and get tokens."""
        try:
            response = requests.post(
                f"{self.api_url}oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error getting Monzo tokens: {str(e)}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh a Monzo access token."""
        try:
            response = requests.post(
                f"{self.api_url}oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error refreshing Monzo token: {str(e)}")
            raise

class TrueLayerAuthProvider(AuthProvider):
    """Authentication provider for TrueLayer."""
    
    def __init__(self, provider_type: AuthProviderType):
        from flask import current_app
        
        self.provider_type = provider_type
        super().__init__(
            name=provider_type.value,
            client_id=current_app.config.get('TRUELAYER_CLIENT_ID'),
            client_secret=current_app.config.get('TRUELAYER_CLIENT_SECRET'),
            redirect_uri=current_app.config.get('TRUELAYER_REDIRECT_URI')
        )
        self.auth_url = "https://auth.truelayer.com/"
        self.api_url = "https://api.truelayer.com/"
    
    def get_auth_url(self, state: str) -> str:
        """Get the TrueLayer authorization URL."""
        return (
            f"{self.auth_url}?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope=info accounts balance cards transactions offline_access"
            f"&providers={self.provider_type.value}"
            f"&state={state}"
        )
    
    def handle_oauth_code_callback(self, code: str) -> Dict[str, Any]:
        """Handle the TrueLayer OAuth callback code and get tokens."""
        try:
            response = requests.post(
                f"{self.api_url}connect/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error getting TrueLayer tokens: {str(e)}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh a TrueLayer access token."""
        try:
            response = requests.post(
                f"{self.api_url}connect/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error refreshing TrueLayer token: {str(e)}")
            raise

# Create a mapping of provider types to provider classes
provider_mapping = {
    AuthProviderType.MONZO: MonzoAuthProvider(),
    AuthProviderType.BARCLAYS: TrueLayerAuthProvider(AuthProviderType.BARCLAYS),
    AuthProviderType.HSBC: TrueLayerAuthProvider(AuthProviderType.HSBC),
    AuthProviderType.SANTANDER: TrueLayerAuthProvider(AuthProviderType.SANTANDER),
    AuthProviderType.LLOYDS: TrueLayerAuthProvider(AuthProviderType.LLOYDS),
    AuthProviderType.NATWEST: TrueLayerAuthProvider(AuthProviderType.NATWEST)
}