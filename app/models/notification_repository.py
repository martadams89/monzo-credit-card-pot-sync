"""Repository for notification database operations."""

import logging
from sqlalchemy import desc
from app.models.notification import Notification

log = logging.getLogger("notification_repository")

class SqlAlchemyNotificationRepository:
    """SQL Alchemy implementation of notification repository."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create(self, user_id, title, message, type="info", link=None):
        """Create a new notification."""
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                link=link
            )
            self.db.session.add(notification)
            self.db.session.commit()
            return notification
        except Exception as e:
            log.error(f"Error creating notification: {e}")
            self.db.session.rollback()
            return None
    
    def get_user_notifications(self, user_id, page=1, per_page=10):
        """Get notifications for a user with pagination."""
        return Notification.query.filter_by(user_id=user_id)\
            .order_by(desc(Notification.created_at))\
            .paginate(page=page, per_page=per_page)
    
    def mark_as_read(self, notification_id, user_id):
        """Mark a notification as read."""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                user_id=user_id
            ).first()
            
            if not notification:
                return False
                
            notification.is_read = True
            self.db.session.commit()
            return True
        except Exception as e:
            log.error(f"Error marking notification as read: {e}")
            self.db.session.rollback()
            return False
    
    def mark_all_as_read(self, user_id):
        """Mark all notifications as read for a user."""
        try:
            Notification.query.filter_by(
                user_id=user_id,
                is_read=False
            ).update({Notification.is_read: True})
            
            self.db.session.commit()
            return True
        except Exception as e:
            log.error(f"Error marking all notifications as read: {e}")
            self.db.session.rollback()
            return False
