"""Repository for cooldown database operations"""

import logging
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from app.models.cooldown import Cooldown

log = logging.getLogger("cooldown_repository")

class SqlAlchemyCooldownRepository:
    """SQL Alchemy implementation of cooldown repository"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def save(self, cooldown):
        """Save a cooldown period"""
        try:
            if not cooldown.id:
                self.db.session.add(cooldown)
            self.db.session.commit()
            return True
        except SQLAlchemyError as e:
            log.error(f"Error saving cooldown: {e}")
            self.db.session.rollback()
            return False
    
    def get_active_cooldown(self, account_id, user_id):
        """Get active cooldown period for an account"""
        now = datetime.utcnow()
        return Cooldown.query.filter_by(
            account_id=account_id,
            user_id=user_id
        ).filter(
            Cooldown.expires_at > now
        ).order_by(
            Cooldown.expires_at.desc()
        ).first()
    
    def clear_cooldowns(self, user_id=None, account_id=None):
        """Clear cooldown periods"""
        try:
            query = Cooldown.query
            
            if user_id:
                query = query.filter_by(user_id=user_id)
                
            if account_id:
                query = query.filter_by(account_id=account_id)
            
            count = query.delete()
            self.db.session.commit()
            return count
        except SQLAlchemyError as e:
            log.error(f"Error clearing cooldowns: {e}")
            self.db.session.rollback()
            return 0
    
    def cleanup_expired(self):
        """Remove expired cooldown periods"""
        try:
            now = datetime.utcnow()
            count = Cooldown.query.filter(
                Cooldown.expires_at <= now
            ).delete()
            
            self.db.session.commit()
            return count
        except SQLAlchemyError as e:
            log.error(f"Error cleaning up expired cooldowns: {e}")
            self.db.session.rollback()
            return 0
