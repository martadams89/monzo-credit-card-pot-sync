import logging
from datetime import datetime
from flask import current_app
from flask_mail import Message
from typing import List, Optional

from app.extensions import db, mail
from app.models.notification import UserNotification
from app.models.user import User
from app.models.monzo import MonzoAccount

log = logging.getLogger(__name__)

def send_notification(user_id: str, title: str, message: str, notification_type: str = "info") -> bool:
    """
    Send a notification to a user through the app.
    
    Args:
        user_id: The ID of the user to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification (info, success, warning, error)
        
    Returns:
        bool: True if notification was sent successfully
    """
    try:
        notification = UserNotification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        
        # Log the notification
        log.info(f"Notification sent to user {user_id}: {title}")
        return True
    except Exception as e:
        log.error(f"Failed to send notification to user {user_id}: {str(e)}")
        db.session.rollback()
        return False

def send_monzo_feed_item(account: MonzoAccount, title: str, message: str) -> bool:
    """
    Send a notification to the Monzo app feed.
    
    Args:
        account: MonzoAccount object
        title: Notification title
        message: Notification message
        
    Returns:
        bool: True if feed item was sent successfully
    """
    from app.services.monzo_api import MonzoAPIService
    
    try:
        monzo_api = MonzoAPIService()
        success = monzo_api.send_feed_item(
            account_id=account.account_id,
            title=title, 
            body=message,
            access_token=account.access_token
        )
        
        if success:
            log.info(f"Monzo feed item sent to account {account.id}: {title}")
            return True
        else:
            log.error(f"Failed to send Monzo feed item to account {account.id}")
            return False
    except Exception as e:
        log.error(f"Error sending Monzo feed item: {str(e)}")
        return False

def send_email(recipient: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """
    Send an email to a recipient.
    
    Args:
        recipient: Email address of recipient
        subject: Email subject
        html_body: HTML content of email
        text_body: Plain text content of email (optional)
        
    Returns:
        bool: True if email was sent successfully
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient],
            html=html_body,
            body=text_body or "Please view this email with an HTML email client."
        )
        mail.send(msg)
        log.info(f"Email sent to {recipient}: {subject}")
        return True
    except Exception as e:
        log.error(f"Failed to send email to {recipient}: {str(e)}")
        return False

def send_security_alert(user: User, event_type: str, details: str, ip_address: str = None) -> bool:
    """
    Send a security alert to a user via email.
    
    Args:
        user: User object
        event_type: Type of security event
        details: Detailed information about the event
        ip_address: IP address where the event occurred
        
    Returns:
        bool: True if alert was sent successfully
    """
    try:
        # Create in-app notification
        send_notification(
            user_id=user.id,
            title=f"Security Alert: {event_type}",
            message=details,
            notification_type="warning"
        )
        
        # Send email alert
        subject = f"Security Alert: {event_type}"
        
        # Prepare context for email template
        context = {
            'user': user,
            'event_type': event_type,
            'details': details,
            'ip_address': ip_address,
            'now': datetime.utcnow()
        }
        
        # Render email templates
        from flask import render_template
        html_content = render_template('email/security_alert.html', **context)
        text_content = render_template('email/security_alert.txt', **context)
        
        # Send the email
        send_email(user.email, subject, html_content, text_content)
        
        log.info(f"Security alert sent to user {user.id}: {event_type}")
        return True
    except Exception as e:
        log.error(f"Failed to send security alert to user {user.id}: {str(e)}")
        return False

def get_user_notifications(user_id: str, limit: int = 10, unread_only: bool = False) -> List[UserNotification]:
    """
    Get notifications for a user.
    
    Args:
        user_id: The ID of the user
        limit: Maximum number of notifications to retrieve
        unread_only: Whether to return only unread notifications
        
    Returns:
        List[UserNotification]: List of notifications
    """
    query = UserNotification.query.filter_by(user_id=user_id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    return query.order_by(UserNotification.created_at.desc()).limit(limit).all()

def mark_notification_as_read(notification_id: str) -> bool:
    """
    Mark a notification as read.
    
    Args:
        notification_id: The ID of the notification to mark as read
        
    Returns:
        bool: True if the notification was successfully marked as read
    """
    try:
        notification = UserNotification.query.get(notification_id)
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()
            return True
        return False
    except Exception as e:
        log.error(f"Error marking notification as read: {str(e)}")
        db.session.rollback()
        return False

def mark_all_notifications_as_read(user_id: str) -> int:
    """
    Mark all notifications for a user as read.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        int: Number of notifications marked as read
    """
    try:
        now = datetime.utcnow()
        result = db.session.query(UserNotification).filter_by(
            user_id=user_id, is_read=False
        ).update({
            'is_read': True,
            'read_at': now
        })
        db.session.commit()
        return result
    except Exception as e:
        log.error(f"Error marking all notifications as read: {str(e)}")
        db.session.rollback()
        return 0
