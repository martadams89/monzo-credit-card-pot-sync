"""
Repository for account database operations.

This module defines the repository pattern implementation for Account model operations,
providing a clean interface for database interactions.
"""

import logging
from sqlalchemy.exc import SQLAlchemyError
from app.models.account import Account

log = logging.getLogger(__name__)

class SqlAlchemyAccountRepository:
    """SQL Alchemy implementation of account repository."""
    
    def __init__(self, db_session):
        """Initialize repository with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def get_all(self):
        """Get all accounts.
        
        Returns:
            list: All accounts
        """
        try:
            return Account.query.all()
        except SQLAlchemyError as e:
            log.error(f"Error retrieving all accounts: {e}")
            return []
    
    def get_by_id(self, account_id):
        """Get account by ID.
        
        Args:
            account_id: Account ID
            
        Returns:
            Account: Account or None if not found
        """
        try:
            return Account.query.get(account_id)
        except SQLAlchemyError as e:
            log.error(f"Error retrieving account {account_id}: {e}")
            return None
    
    def get_by_user_id(self, user_id):
        """Get all accounts for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            list: User's accounts
        """
        try:
            return Account.query.filter_by(user_id=user_id).all()
        except SQLAlchemyError as e:
            log.error(f"Error retrieving accounts for user {user_id}: {e}")
            return []
    
    def get_by_type(self, user_id, account_type):
        """Get account by type for a user.
        
        Args:
            user_id: User ID
            account_type: Account type
            
        Returns:
            Account: Account or None if not found
        """
        try:
            return Account.query.filter_by(user_id=user_id, type=account_type).first()
        except SQLAlchemyError as e:
            log.error(f"Error retrieving {account_type} account for user {user_id}: {e}")
            return None
    
    def save(self, account):
        """Save an account.
        
        Args:
            account: Account to save
            
        Returns:
            Account: Saved account or None if failed
        """
        try:
            if not account.id:  # New account
                self.db.session.add(account)
            self.db.session.commit()
            return account
        except SQLAlchemyError as e:
            log.error(f"Error saving account: {e}")
            self.db.session.rollback()
            return None
    
    def delete(self, account_id):
        """Delete an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            bool: True if successful
        """
        try:
            account = self.get_by_id(account_id)
            if account:
                self.db.session.delete(account)
                self.db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            log.error(f"Error deleting account {account_id}: {e}")
            self.db.session.rollback()
            return False