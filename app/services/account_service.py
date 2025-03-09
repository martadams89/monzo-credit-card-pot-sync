"""
Service for account management operations.

This service handles operations related to user accounts, including retrieving,
creating, updating, and managing account connections with external providers.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from sqlalchemy.exc import SQLAlchemyError

from app.models.account import Account
from app.clients.monzo_client import MonzoClient
from app.clients.truelayer_client import TrueLayerClient

log = logging.getLogger(__name__)

class AccountService:
    """
    Service for managing user accounts and their connections to external services.
    
    This service provides methods for retrieving account information, updating
    access tokens, and managing the connection between users and their financial accounts.
    """
    
    def __init__(self, db_session=None, account_repository=None, 
                 monzo_client=None, truelayer_client=None, setting_repository=None):
        """Initialize AccountService.
        
        Args:
            db_session: SQLAlchemy database session
            account_repository: Repository for account data
            monzo_client: Client for Monzo API
            truelayer_client: Client for TrueLayer API
            setting_repository: Repository for settings
        """
        self.db = db_session
        self.account_repository = account_repository
        self.monzo_client = monzo_client
        self.truelayer_client = truelayer_client
        self.setting_repository = setting_repository
    
    def get_all_accounts(self) -> List[Account]:
        """Get all accounts across all users.
        
        Returns:
            list: All accounts
        """
        try:
            if self.account_repository:
                return self.account_repository.get_all()
            elif self.db:
                return Account.query.all()
            
            log.error("No database session or repository available")
            return []
        except Exception as e:
            log.error(f"Error retrieving accounts: {str(e)}")
            return []
    
    def get_user_accounts(self, user_id: int) -> List[Account]:
        """Get all accounts for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            list: User's accounts
        """
        try:
            if self.account_repository:
                return self.account_repository.get_by_user_id(user_id)
            elif self.db:
                return Account.query.filter_by(user_id=user_id).all()
            
            log.error("No database session or repository available")
            return []
        except Exception as e:
            log.error(f"Error retrieving accounts for user {user_id}: {str(e)}")
            return []
    
    def get_user_monzo_account(self, user_id: int) -> Optional[Account]:
        """Get the Monzo account for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Account: Monzo account or None
        """
        try:
            if self.account_repository:
                accounts = self.account_repository.get_by_user_id(user_id)
                for account in accounts:
                    if account.type.lower() == "monzo":
                        return account
            elif self.db:
                return Account.query.filter_by(user_id=user_id, type="Monzo").first()
            
            return None
        except Exception as e:
            log.error(f"Error retrieving Monzo account for user {user_id}: {str(e)}")
            return None
    
    def get_account(self, account_id: int) -> Optional[Account]:
        """Get an account by ID.
        
        Args:
            account_id: Account ID
            
        Returns:
            Account: Account or None
        """
        try:
            if self.account_repository:
                return self.account_repository.get_by_id(account_id)
            elif self.db:
                return Account.query.get(account_id)
            
            log.error("No database session or repository available")
            return None
        except Exception as e:
            log.error(f"Error retrieving account {account_id}: {str(e)}")
            return None
    
    def create_account(self, user_id: int, account_type: str, access_token: str,
                      refresh_token: str, token_expiry: int, account_id: str = None,
                      pot_id: str = None) -> Optional[Account]:
        """Create a new account.
        
        Args:
            user_id: User ID
            account_type: Account type (e.g., "Monzo", "Amex")
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expiry: Token expiry timestamp
            account_id: External account ID (optional)
            pot_id: Monzo pot ID (optional)
            
        Returns:
            Account: Created account or None if failed
        """
        try:
            account = Account(
                user_id=user_id,
                type=account_type,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry,
                account_id=account_id,
                pot_id=pot_id
            )
            
            if self.account_repository:
                return self.account_repository.save(account)
            elif self.db:
                self.db.session.add(account)
                self.db.session.commit()
                return account
            
            log.error("No database session or repository available")
            return None
        except SQLAlchemyError as e:
            log.error(f"Database error creating account: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return None
        except Exception as e:
            log.error(f"Error creating account: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return None
    
    def update_account(self, account_id: int, **kwargs) -> Optional[Account]:
        """Update an existing account.
        
        Args:
            account_id: Account ID
            **kwargs: Fields to update
            
        Returns:
            Account: Updated account or None if failed
        """
        try:
            account = self.get_account(account_id)
            if not account:
                log.error(f"Account {account_id} not found")
                return None
                
            # Update fields from kwargs
            for key, value in kwargs.items():
                if hasattr(account, key):
                    setattr(account, key, value)
            
            if self.account_repository:
                return self.account_repository.save(account)
            elif self.db:
                self.db.session.commit()
                return account
            
            log.error("No database session or repository available")
            return None
        except SQLAlchemyError as e:
            log.error(f"Database error updating account {account_id}: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return None
        except Exception as e:
            log.error(f"Error updating account {account_id}: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return None
    
    def delete_account(self, account_id: int) -> bool:
        """Delete an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            bool: True if successful
        """
        try:
            account = self.get_account(account_id)
            if not account:
                log.error(f"Account {account_id} not found")
                return False
                
            if self.account_repository:
                return self.account_repository.delete(account_id)
            elif self.db:
                self.db.session.delete(account)
                self.db.session.commit()
                return True
            
            log.error("No database session or repository available")
            return False
        except Exception as e:
            log.error(f"Error deleting account {account_id}: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return False
    
    def refresh_token(self, account: Account) -> bool:
        """Refresh an account's OAuth token.
        
        Args:
            account: Account to refresh
            
        Returns:
            bool: True if successful
        """
        try:
            # Check if we need to refresh
            current_time = int(time.time())
            if account.token_expiry and account.token_expiry > current_time + 300:
                # Token still valid for at least 5 more minutes
                return True
                
            if not account.refresh_token:
                log.error(f"No refresh token for account {account.id}")
                return False
            
            # Choose the right client based on account type
            client = None
            if account.type.lower() == "monzo":
                if self.monzo_client:
                    client = self.monzo_client
                else:
                    # Create Monzo client from settings
                    monzo_client_id = self.setting_repository.get("monzo_client_id")
                    monzo_client_secret = self.setting_repository.get("monzo_client_secret")
                    monzo_redirect_uri = self.setting_repository.get("monzo_redirect_uri")
                    
                    if monzo_client_id and monzo_client_secret and monzo_redirect_uri:
                        client = MonzoClient(monzo_client_id, monzo_client_secret, monzo_redirect_uri)
            else:
                # Assume TrueLayer-based provider
                if self.truelayer_client:
                    client = self.truelayer_client
                else:
                    # Create TrueLayer client from settings
                    truelayer_client_id = self.setting_repository.get("truelayer_client_id")
                    truelayer_client_secret = self.setting_repository.get("truelayer_client_secret")
                    truelayer_redirect_uri = self.setting_repository.get("truelayer_redirect_uri")
                    
                    if truelayer_client_id and truelayer_client_secret and truelayer_redirect_uri:
                        client = TrueLayerClient(truelayer_client_id, truelayer_client_secret, truelayer_redirect_uri)
            
            if not client:
                log.error(f"No API client available for account type {account.type}")
                return False
            
            # Refresh the token
            response = client.refresh_token(account.refresh_token)
            
            if not response:
                log.error(f"Failed to refresh token for account {account.id}")
                return False
                
            # Update account with new tokens
            if 'access_token' in response:
                account.access_token = response['access_token']
            if 'refresh_token' in response:
                account.refresh_token = response['refresh_token']
            if 'expires_in' in response:
                account.token_expiry = int(time.time()) + response['expires_in']
            
            # Save changes
            if self.account_repository:
                self.account_repository.save(account)
            elif self.db:
                self.db.session.commit()
            else:
                log.error("No database session or repository available")
                return False
                
            log.info(f"Token refreshed for account {account.id}")
            return True
        except Exception as e:
            log.error(f"Error refreshing token for account {account.id}: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return False
    
    def update_last_synced(self, account_id: int) -> bool:
        """Update the last_synced_at timestamp for an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            bool: True if successful
        """
        try:
            from datetime import datetime
            return self.update_account(account_id, last_synced_at=datetime.utcnow()) is not None
        except Exception as e:
            log.error(f"Error updating last_synced for account {account_id}: {str(e)}")
            return False
    
    def map_pot(self, account_id: int, pot_id: str) -> bool:
        """Map a Monzo pot to an account.
        
        Args:
            account_id: Account ID
            pot_id: Monzo pot ID
            
        Returns:
            bool: True if successful
        """
        try:
            return self.update_account(account_id, pot_id=pot_id) is not None
        except Exception as e:
            log.error(f"Error mapping pot for account {account_id}: {str(e)}")
            return False
