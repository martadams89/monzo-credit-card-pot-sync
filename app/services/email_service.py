"""Service for email functionality."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails."""
    
    def __init__(self, setting_repository, config=None):
        """Initialize the email service.
        
        Args:
            setting_repository: Repository for accessing settings
            config: App configuration dictionary
        """
        self.setting_repository = setting_repository
        self.config = config or {}
    
    def _get_smtp_settings(self):
        """Get SMTP settings from repository or config."""
        settings = {
            'server': self.setting_repository.get('smtp_server', self.config.get('MAIL_SERVER')),
            'port': int(self.setting_repository.get('smtp_port', self.config.get('MAIL_PORT', 587))),
            'username': self.setting_repository.get('smtp_username', self.config.get('MAIL_USERNAME')),
            'password': self.setting_repository.get('smtp_password', self.config.get('MAIL_PASSWORD')),
            'use_tls': self.setting_repository.get('smtp_use_tls', self.config.get('MAIL_USE_TLS', 'true')).lower() in ('true', '1', 'yes'),
            'default_sender': self.setting_repository.get('mail_default_sender', self.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com'))
        }
        return settings
    
    def send_email(self, subject, recipients, body, html=None):
        """Send an email.
        
        Args:
            subject: Email subject
            recipients: List of recipient email addresses
            body: Plain text email body
            html: Optional HTML email body
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        settings = self._get_smtp_settings()
        
        if not settings['server'] or not settings['port']:
            logger.error("SMTP server not configured")
            return False
        
        if isinstance(recipients, str):
            recipients = [recipients]
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings['default_sender']
            msg['To'] = ', '.join(recipients)
            
            # Attach plain text and HTML parts
            msg.attach(MIMEText(body, 'plain'))
            if html:
                msg.attach(MIMEText(html, 'html'))
            
            # Connect to SMTP server
            if settings['use_tls']:
                smtp = smtplib.SMTP(settings['server'], settings['port'])
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(settings['server'], settings['port'])
            
            # Login if credentials provided
            if settings['username'] and settings['password']:
                smtp.login(settings['username'], settings['password'])
            
            # Send email
            smtp.sendmail(settings['default_sender'], recipients, msg.as_string())
            smtp.quit()
            
            logger.info(f"Sent email '{subject}' to {len(recipients)} recipients")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_template_email(self, subject, recipients, template, context=None):
        """Send an email using a template.
        
        Args:
            subject: Email subject
            recipients: List of recipient email addresses
            template: Template name (without extension)
            context: Optional dictionary of template variables
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        context = context or {}
        
        try:
            from flask import render_template
            
            # Render template
            text_body = render_template(f"emails/{template}.txt", **context)
            html_body = render_template(f"emails/{template}.html", **context)
            
            return self.send_email(subject, recipients, text_body, html_body)
        except Exception as e:
            logger.error(f"Error sending template email: {str(e)}")
            return False
    
    def send_sync_report(self, user_email, report_data):
        """Send a synchronization report email.
        
        Args:
            user_email: Recipient email address
            report_data: Dictionary containing sync report data
            
        Returns:
            bool: True if email was sent, False otherwise
        """
        subject = "Sync Report: "
        if report_data.get('status') == 'success':
            subject += "Successful Synchronization"
        elif report_data.get('status') == 'partial':
            subject += "Partial Synchronization"
        else:
            subject += "Failed Synchronization"
        
        return self.send_template_email(
            subject=subject,
            recipients=[user_email],
            template="sync_report",
            context={"report": report_data}
        )
