"""Service for managing Monzo pot mappings."""

import logging
import json
from app.extensions import db
from app.models.setting import Setting

logger = logging.getLogger(__name__)

class PotService:
    """Service for managing pot mappings between credit cards and Monzo pots."""
    
    def __init__(self, setting_repository):
        """Initialize the pot service with settings repository."""
        self.setting_repository = setting_repository
    
    def get_pot_mappings(self, user_id):
        """
        Get pot mappings for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            dict: Mapping of credit card IDs to pot IDs
        """
        mapping_key = f'pot_mappings:{user_id}'
        mapping_json = self.setting_repository.get(mapping_key)
        
        if not mapping_json:
            return {}
            
        try:
            return json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.error(f"Invalid pot mapping JSON for user {user_id}")
            return {}
    
    def update_pot_mappings(self, user_id, mappings):
        """
        Update pot mappings for a user.
        
        Args:
            user_id: The user ID
            mappings: Dictionary mapping credit card IDs to pot IDs
            
        Returns:
            bool: True if successful, False otherwise
        """
        mapping_key = f'pot_mappings:{user_id}'
        
        try:
            mapping_json = json.dumps(mappings)
            self.setting_repository.save_setting(mapping_key, mapping_json)
            return True
        except Exception as e:
            logger.error(f"Error updating pot mappings for user {user_id}: {str(e)}")
            return False
    
    def remove_account_mappings(self, account_id):
        """
        Remove mappings for a specific account.
        
        Args:
            account_id: The account ID to remove mappings for
            
        Returns:
            bool: True if mappings were removed, False otherwise
        """
        try:
            # Get the account to find the user ID
            from app.models.account import Account
            account = Account.query.get(account_id)
            if not account:
                return False
                
            user_id = account.user_id
            
            # Get existing mappings
            mappings = self.get_pot_mappings(user_id)
            
            # Remove the account from mappings
            account_id_str = str(account_id)
            if account_id_str in mappings:
                del mappings[account_id_str]
                return self.update_pot_mappings(user_id, mappings)
            
            return True
        except Exception as e:
            logger.error(f"Error removing account mappings for account {account_id}: {str(e)}")
            return False
    
    def get_mapped_accounts(self, user_id):
        """
        Get a list of accounts that have pot mappings.
        
        Args:
            user_id: The user ID
            
        Returns:
            list: List of account IDs with mappings
        """
        mappings = self.get_pot_mappings(user_id)
        return list(mappings.keys())
    
    def get_mapped_pot(self, user_id, account_id):
        """
        Get the pot ID mapped to a specific account.
        
        Args:
            user_id: The user ID
            account_id: The account ID
            
        Returns:
            str: Pot ID or None if not found
        """
        mappings = self.get_pot_mappings(user_id)
        return mappings.get(str(account_id))
    
    def set_mapped_pot(self, user_id, account_id, pot_id):
        """
        Set the pot mapping for a specific account.
        
        Args:
            user_id: The user ID
            account_id: The account ID
            pot_id: The pot ID to map to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get existing mappings
            mappings = self.get_pot_mappings(user_id)
            
            # Update or add the mapping
            mappings[str(account_id)] = pot_id
            
            # Save the updated mappings
            return self.update_pot_mappings(user_id, mappings)
        except Exception as e:
            logger.error(f"Error setting pot mapping for user {user_id}, account {account_id}: {str(e)}")
            return False
