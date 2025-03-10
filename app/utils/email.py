import logging
from flask import current_app, render_template, url_for
from flask_mail import Message
from datetime import datetime
from app.extensions import mail

logger = logging.getLogger(__name__)

def send_email(subject, recipients, html_body, text_body=None):
    """Send an email with the given parameters."""
    try:
        msg = Message(
            subject=subject,
            recipients=recipients,
            html=html_body,
            body=text_body or html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        mail.send(msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_verification_email(user):
    """Send email verification link to the user."""
    verification_url = url_for(
        'auth.verify_email', 
        token=user.verification_token,
        _external=True
    )
    
    # Context for the email template
    context = {
        'user': user,
        'url': verification_url,
        'now': datetime.utcnow()
    }
    
    # Render the email templates
    html = render_template('email/verify_email.html', **context)
    text = render_template('email/verify_email.txt', **context)
    
    return send_email(
        subject="Verify Your Email Address",
        recipients=[user.email],
        html_body=html,
        text_body=text
    )

def send_password_reset_email(user):
    """Send password reset link to the user."""
    reset_url = url_for(
        'auth.reset_password', 
        token=user.reset_token,
        _external=True
    )
    
    # Context for the email template
    context = {
        'user': user,
        'url': reset_url,
        'now': datetime.utcnow()
    }
    
    # Render the email templates
    html = render_template('email/reset_password.html', **context)
    text = render_template('email/reset_password.txt', **context)
    
    return send_email(
        subject="Reset Your Password",
        recipients=[user.email],
        html_body=html,
        text_body=text
    )

def send_security_alert(user, event_type, details, ip_address=None):
    """Send security alert to the user."""
    # Context for the email template
    context = {
        'user': user,
        'event_type': event_type,
        'details': details,
        'ip_address': ip_address,
        'now': datetime.utcnow()
    }
    
    # Render the email templates
    html = render_template('email/security_alert.html', **context)
    text = render_template('email/security_alert.txt', **context)
    
    return send_email(
        subject="Security Alert - Monzo Sync",
        recipients=[user.email],
        html_body=html,
        text_body=text
    )
