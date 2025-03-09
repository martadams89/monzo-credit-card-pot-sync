"""Service for managing cooldown periods after deposits/withdrawals."""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from app.models.cooldown import Cooldown

log = logging.getLogger(__name__)

class CooldownService:
    """Service for managing cooldown periods between pot adjustments."""
    
    def __init__(self, db_session=None, cooldown_repository=None):
        """Initialize CooldownService.
        
        Args:
            db_session: SQLAlchemy database session
            cooldown_repository: Repository for cooldown data
        """
        self.db = db_session
        self.cooldown_repository = cooldown_repository
    
    def start_cooldown(self, account_id: str, user_id: int, hours: int, 
                       initial_balance: Optional[int] = None):
        """Start a cooldown period for an account.
        
        Args:
            account_id: Account ID
            user_id: User ID
            hours: Number of hours for cooldown
            initial_balance: Initial balance at start of cooldown
            
        Returns:
            Cooldown: Cooldown object or None if failed
        """
        try:
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=hours)
            
            cooldown = Cooldown(
                account_id=account_id,
                user_id=user_id,
                expires_at=expires_at,
                initial_balance=initial_balance
            )
            
            if self.cooldown_repository:
                self.cooldown_repository.save(cooldown)
            elif self.db:
                self.db.session.add(cooldown)
                self.db.session.commit()
            else:
                log.error("No database session or repository available")
                return None
            
            log.info(f"Started cooldown for account {account_id} until {expires_at}")
            return cooldown
            
        except Exception as e:
            log.error(f"Error starting cooldown: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return None
    
    def get_active_cooldown(self, account_id: str, user_id: int):
        """Get the active cooldown period for an account.
        
        Args:
            account_id: Account ID
            user_id: User ID
            
        Returns:
            Cooldown: Active cooldown or None
        """
        try:
            if self.cooldown_repository:
                return self.cooldown_repository.get_active_cooldown(account_id, user_id)
            elif self.db:
                now = datetime.utcnow()
                return Cooldown.query.filter_by(
                    account_id=account_id,
                    user_id=user_id
                ).filter(
                    Cooldown.expires_at > now
                ).order_by(
                    Cooldown.expires_at.desc()
                ).first()
            
            log.error("No database session or repository available")
            return None
            
        except Exception as e:
            log.error(f"Error getting active cooldown: {str(e)}")
            return None
    
    def is_in_cooldown(self, account_id: str, user_id: int) -> bool:
        """Check if an account is in cooldown period.
        
        Args:
            account_id: Account ID
            user_id: User ID
            
        Returns:
            bool: True if in cooldown, False otherwise
        """
        cooldown = self.get_active_cooldown(account_id, user_id)
        return cooldown is not None
    
    def get_remaining_time(self, account_id: str, user_id: int) -> int:
        """Get remaining cooldown time in seconds.
        
        Args:
            account_id: Account ID
            user_id: User ID
            
        Returns:
            int: Remaining time in seconds, 0 if not in cooldown
        """
        cooldown = self.get_active_cooldown(account_id, user_id)
        if not cooldown:
            return 0
            
        now = datetime.utcnow()
        if now >= cooldown.expires_at:
            return 0
            
        return int((cooldown.expires_at - now).total_seconds())
    
    def clear_cooldown(self, account_id: str = None, user_id: int = None) -> int:
        """Clear cooldown periods.
        
        Args:
            account_id: Optional account ID filter
            user_id: Optional user ID filter
            
        Returns:
            int: Number of cooldowns cleared
        """
        try:
            if self.cooldown_repository:
                return self.cooldown_repository.clear_cooldowns(user_id, account_id)
            elif self.db:
                query = Cooldown.query
                
                if user_id:
                    query = query.filter_by(user_id=user_id)
                    
                if account_id:
                    query = query.filter_by(account_id=account_id)
                
                count = query.delete()
                self.db.session.commit()
                return count
            
            log.error("No database session or repository available")
            return 0
            
        except Exception as e:
            log.error(f"Error clearing cooldown: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return 0
    
    def cleanup_expired(self) -> int:
        """Clean up expired cooldown periods.
        
        Returns:
            int: Number of cooldowns removed
        """
        try:
            if self.cooldown_repository:
                return self.cooldown_repository.cleanup_expired()
            elif self.db:
                now = datetime.utcnow()
                count = Cooldown.query.filter(
                    Cooldown.expires_at <= now
                ).delete()
                
                self.db.session.commit()
                return count
            
            log.error("No database session or repository available")
            return 0
            
        except Exception as e:
            log.error(f"Error cleaning up expired cooldowns: {str(e)}")
            if self.db:
                self.db.session.rollback()
            return 0
