"""
Service for processing and managing cooldown events.

This service handles the analysis and processing of account cooldowns,
helping prevent excessive account operations.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

class CooldownProcessor:
    """Service for processing account cooldowns."""
    
    def __init__(self, cooldown_service=None, account_service=None):
        """Initialize CooldownProcessor.
        
        Args:
            cooldown_service: Service for managing cooldown periods
            account_service: Service for managing accounts
        """
        self.cooldown_service = cooldown_service
        self.account_service = account_service
    
    def process_expired_cooldowns(self) -> Dict[str, Any]:
        """Process expired cooldowns and clean them up.
        
        Returns:
            dict: Results of the cleanup operation
        """
        if not self.cooldown_service:
            log.error("Cooldown service not available")
            return {"status": "error", "message": "Cooldown service not available", "removed": 0}
        
        try:
            # Remove expired cooldowns
            removed_count = self.cooldown_service.cleanup_expired()
            
            result = {
                "status": "success",
                "message": f"Removed {removed_count} expired cooldowns",
                "removed": removed_count
            }
            
            log.info(f"Removed {removed_count} expired cooldowns")
            return result
        except Exception as e:
            log.error(f"Error processing expired cooldowns: {str(e)}")
            return {"status": "error", "message": str(e), "removed": 0}
    
    def get_active_cooldowns(self, user_id=None) -> List[Dict[str, Any]]:
        """Get information about active cooldowns.
        
        Args:
            user_id: Optional filter by user ID
            
        Returns:
            list: Active cooldown information
        """
        if not self.cooldown_service or not self.account_service:
            log.error("Required services not available")
            return []
        
        try:
            # Get accounts
            if user_id:
                accounts = self.account_service.get_user_accounts(user_id)
            else:
                accounts = self.account_service.get_all_accounts()
            
            # Build account lookup dict
            account_map = {account.account_id: account for account in accounts}
            
            # Get active cooldowns
            result = []
            
            for account in accounts:
                cooldown = self.cooldown_service.get_active_cooldown(account.account_id, account.user_id)
                
                if cooldown:
                    # Get remaining time
                    remaining = self.cooldown_service.get_remaining_time(account.account_id, account.user_id)
                    
                    cooldown_info = {
                        "account_id": account.account_id,
                        "external_id": account.account_id,
                        "account_type": account.type,
                        "user_id": account.user_id,
                        "started_at": cooldown.started_at,
                        "expires_at": cooldown.expires_at,
                        "remaining_seconds": remaining,
                        "initial_balance": cooldown.initial_balance
                    }
                    
                    result.append(cooldown_info)
            
            return result
        except Exception as e:
            log.error(f"Error getting active cooldowns: {str(e)}")
            return []
    
    def create_cooldown(self, account_id, user_id, hours, initial_balance=None) -> Dict[str, Any]:
        """Create a new cooldown period.
        
        Args:
            account_id: Account ID
            user_id: User ID
            hours: Cooldown duration in hours
            initial_balance: Initial balance at start of cooldown
            
        Returns:
            dict: Result of the operation
        """
        if not self.cooldown_service:
            log.error("Cooldown service not available")
            return {"status": "error", "message": "Cooldown service not available"}
        
        try:
            # Check if already in cooldown
            if self.cooldown_service.is_in_cooldown(account_id, user_id):
                return {
                    "status": "error",
                    "message": "Account already in cooldown",
                    "cooldown_remaining": self.cooldown_service.get_remaining_time(account_id, user_id)
                }
            
            # Create new cooldown
            cooldown = self.cooldown_service.start_cooldown(account_id, user_id, hours, initial_balance)
            
            if cooldown:
                return {
                    "status": "success",
                    "message": f"Cooldown created for {hours} hours",
                    "cooldown": {
                        "expires_at": cooldown.expires_at,
                        "hours": hours
                    }
                }
            else:
                return {"status": "error", "message": "Failed to create cooldown"}
        except Exception as e:
            log.error(f"Error creating cooldown: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def clear_cooldown(self, account_id=None, user_id=None) -> Dict[str, Any]:
        """Clear one or more cooldowns.
        
        Args:
            account_id: Optional account ID filter
            user_id: Optional user ID filter
            
        Returns:
            dict: Result of the operation
        """
        if not self.cooldown_service:
            log.error("Cooldown service not available")
            return {"status": "error", "message": "Cooldown service not available", "removed": 0}
        
        try:
            # Remove cooldowns matching filters
            removed_count = self.cooldown_service.clear_cooldown(account_id, user_id)
            
            result = {
                "status": "success",
                "message": f"Removed {removed_count} cooldowns",
                "removed": removed_count
            }
            
            log.info(f"Cleared {removed_count} cooldowns")
            return result
        except Exception as e:
            log.error(f"Error clearing cooldowns: {str(e)}")
            return {"status": "error", "message": str(e), "removed": 0}
