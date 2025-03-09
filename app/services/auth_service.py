"""Authentication service for the application."""

import logging
import time
import secrets
from urllib.parse import urlencode
import requests
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app, url_for
from app.extensions import db
from app.models.user import User
from app.models.account import Account

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling authentication-related operations."""
    
    def __init__(self, user_repository, setting_repository):
        """Initialize the auth service."""
        self.user_repository = user_repository
        self.setting_repository = setting_repository
        self._serializer = None
    
    @property
    def serializer(self):
        """Get the serializer for token generation."""
        if self._serializer is None and current_app:
            self._serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return self._serializer
    
    def generate_oauth_state(self, user_id=None):
        """Generate and store OAuth state for CSRF protection."""
        state = secrets.token_urlsafe(32)
        key = f"oauth_state:{state}"
        
        # Store state in settings with user ID
        value = str(user_id) if user_id else ""
        self.setting_repository.save_setting(key, value)
        
        return state
    
    def verify_oauth_state(self, state):
        """Verify OAuth state and return associated user ID if any."""
        key = f"oauth_state:{state}"
        value = self.setting_repository.get(key)
        
        # Remove state after use (one-time use)
        if value is not None:
            self.setting_repository.delete(key)
            return True
            
        return False
    
    def get_monzo_auth_url(self, user_id=None):
        """Get Monzo authorization URL for OAuth flow."""
        client_id = self.setting_repository.get('monzo_client_id')
        redirect_uri = self.setting_repository.get('monzo_redirect_uri', 
                                               current_app.config.get('MONZO_REDIRECT_URI'))
        
        if not client_id or not redirect_uri:
            logger.error("Missing Monzo OAuth credentials")
            return None
        
        state = self.generate_oauth_state(user_id)
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state
        }
        
        return f"https://auth.monzo.com/?{urlencode(params)}"
    
    def complete_monzo_auth(self, code, user_id=None):
        """Complete Monzo OAuth flow by exchanging code for tokens."""
        client_id = self.setting_repository.get('monzo_client_id')
        client_secret = self.setting_repository.get('monzo_client_secret')
        redirect_uri = self.setting_repository.get('monzo_redirect_uri',
                                               current_app.config.get('MONZO_REDIRECT_URI'))
        
        if not client_id or not client_secret or not redirect_uri:
            logger.error("Missing Monzo OAuth credentials")
            return False
        
        # Exchange code for tokens
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        try:
            response = requests.post('https://api.monzo.com/oauth2/token', data=data)
            response.raise_for_status()
            tokens = response.json()
            
            # Create or update account
            account = Account(
                user_id=user_id,
                type='monzo',
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token'],
                token_expiry=int(time.time()) + tokens['expires_in']
            )
            
            db.session.add(account)
            db.session.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error completing Monzo OAuth: {str(e)}")
            return False
    
    def get_truelayer_auth_url(self, user_id=None):
        """Get TrueLayer authorization URL for OAuth flow."""
        client_id = self.setting_repository.get('truelayer_client_id')
        redirect_uri = self.setting_repository.get('truelayer_redirect_uri',
                                               current_app.config.get('TRUELAYER_REDIRECT_URI'))
        
        if not client_id or not redirect_uri:
            logger.error("Missing TrueLayer OAuth credentials")
            return None
        
        state = self.generate_oauth_state(user_id)
        
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'scope': 'info accounts balance cards transactions',
            'redirect_uri': redirect_uri,
            'providers': 'uk-ob-all uk-oauth-all',
            'state': state
        }
        
        return f"https://auth.truelayer.com/?{urlencode(params)}"
    
    def complete_truelayer_auth(self, code, user_id=None):
        """Complete TrueLayer OAuth flow by exchanging code for tokens."""
        client_id = self.setting_repository.get('truelayer_client_id')
        client_secret = self.setting_repository.get('truelayer_client_secret')
        redirect_uri = self.setting_repository.get('truelayer_redirect_uri',
                                               current_app.config.get('TRUELAYER_REDIRECT_URI'))
        
        if not client_id or not client_secret or not redirect_uri:
            logger.error("Missing TrueLayer OAuth credentials")
            return False
            
        # Exchange code for tokens
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        try:
            response = requests.post('https://auth.truelayer.com/connect/token', data=data)
            response.raise_for_status()
            tokens = response.json()
            
            # Get provider info
            headers = {'Authorization': f"Bearer {tokens['access_token']}"}
            info_response = requests.get('https://api.truelayer.com/data/v1/me', headers=headers)
            info_response.raise_for_status()
            info = info_response.json()
            
            # Determine card provider - use provider name if available, fallback to results type
            provider_name = None
            if 'results' in info and info['results']:
                provider_info = info['results'][0].get('provider', {})
                provider_name = provider_info.get('display_name')
            
            # Use a default name if no provider info available
            if not provider_name:
                provider_name = 'Credit Card'
            
            # Create account - remove the name parameter
            account = Account(
                user_id=user_id,
                type='credit_card',
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token'],
                token_expiry=int(time.time()) + tokens['expires_in']
            )
            
            db.session.add(account)
            db.session.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error completing TrueLayer OAuth: {str(e)}")
            return False
    
    # Password reset functionality
    def generate_reset_token(self, user):
        """Generate password reset token for a user."""
        payload = {'user_id': user.id, 'type': 'password_reset'}
        return self.serializer.dumps(payload)
        
    def verify_reset_token(self, token, expiration=3600):
        """Verify a password reset token."""
        try:
            payload = self.serializer.loads(token, max_age=expiration)
            if payload.get('type') != 'password_reset':
                return None
            user_id = payload.get('user_id')
            return User.query.get(user_id)
        except (SignatureExpired, BadSignature):
            return None
