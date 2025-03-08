"""Service for managing deposit cooldown periods"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger("cooldown_service")

class CooldownService:
    """Service for managing deposit cooldown periods"""
    
    def __init__(self, db_session):
        self.db = db_session
        
    def is_account_on_cooldown(self, account_type):
        """Check if an account is currently on cooldown"""
        try:
            from app.models.cooldown import Cooldown
            
            cooldown = Cooldown.query.filter_by(account_type=account_type).first()
            if not cooldown:
                return False
                
            return cooldown.expires_at > datetime.now()
        except SQLAlchemyError as e:
            log.error(f"Database error checking cooldown: {e}")
            return False
            
    def set_cooldown(self, account_type, hours):
        """Set a cooldown period for an account"""
        try:
            from app.models.cooldown import Cooldown
            
            expiry = datetime.now() + timedelta(hours=hours)
            cooldown = Cooldown.query.filter_by(account_type=account_type).first()
            
            if cooldown:
                cooldown.expires_at = expiry
            else:
                cooldown = Cooldown(account_type=account_type, expires_at=expiry)
                self.db.session.add(cooldown)
                
            self.db.session.commit()
            log.info(f"Cooldown set for account {account_type} until {expiry}")
            return True
        except SQLAlchemyError as e:
            log.error(f"Database error setting cooldown: {e}")
            self.db.session.rollback()
            return False
            
    def clear_cooldown(self, account_type=None):
        """Clear cooldown for a specific account or all accounts"""
        try:
            from app.models.cooldown import Cooldown
            
            if account_type:
                # Clear specific account cooldown
                cooldown = Cooldown.query.filter_by(account_type=account_type).first()
                if cooldown:
                    self.db.session.delete(cooldown)
            else:
                # Clear all cooldowns
                Cooldown.query.delete()
                
            self.db.session.commit()
            log_msg = f"Cooldown cleared for account {account_type}" if account_type else "All cooldowns cleared"
            log.info(log_msg)
            return True
        except SQLAlchemyError as e:
            log.error(f"Database error clearing cooldown: {e}")
            self.db.session.rollback()
            return False
