"""Service for sending emails"""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, PackageLoader, select_autoescape

log = logging.getLogger("email_service")

class EmailService:
    """Service for sending emails"""
    
    def __init__(self, settings_repository):
        self.settings_repository = settings_repository
        self.jinja_env = Environment(
            loader=PackageLoader('app', 'templates/emails'),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
    def send_email(self, recipient, subject, template_name, context=None):
        """Send an email using configured SMTP settings"""
        if context is None:
            context = {}
            
        # Get email configuration from settings
        smtp_server = self.settings_repository.get("email_smtp_server")
        smtp_port = int(self.settings_repository.get("email_smtp_port") or 587)
        smtp_username = self.settings_repository.get("email_smtp_username")
        smtp_password = self.settings_repository.get("email_smtp_password")
        from_email = self.settings_repository.get("email_from_address")
        use_tls = self.settings_repository.get("email_use_tls") == "True"
        
        # Check if email is configured
        if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_email]):
            log.error("Email settings not fully configured. Cannot send email.")
            return False
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = from_email
            message["To"] = recipient
            
            # Get email templates
            html_template = self.jinja_env.get_template(f"{template_name}.html")
            text_template = self.jinja_env.get_template(f"{template_name}.txt")
            
            # Render templates
            html_content = html_template.render(**context)
            text_content = text_template.render(**context)
            
            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)
            
            # Send email
            if use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls(context=context)
                    server.login(smtp_username, smtp_password)
                    server.sendmail(from_email, recipient, message.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    server.sendmail(from_email, recipient, message.as_string())
                    
            log.info(f"Email sent to {recipient}: {subject}")
            return True
            
        except Exception as e:
            log.error(f"Failed to send email: {e}", exc_info=True)
            return False
            
    def send_verification_email(self, user, verification_link):
        """Send email verification link to user"""
        return self.send_email(
            recipient=user.email,
            subject="Verify Your Email - Monzo Credit Card Pot Sync",
            template_name="email_verification",
            context={
                "username": user.username,
                "verification_link": verification_link
            }
        )
        
    def send_password_reset_email(self, user, reset_link):
        """Send password reset link to user"""
        return self.send_email(
            recipient=user.email,
            subject="Reset Your Password - Monzo Credit Card Pot Sync",
            template_name="password_reset",
            context={
                "username": user.username,
                "reset_link": reset_link
            }
        )
        
    def send_two_factor_code(self, user, code):
        """Send two-factor authentication code to user"""
        return self.send_email(
            recipient=user.email,
            subject="Your Login Verification Code - Monzo Credit Card Pot Sync",
            template_name="two_factor_code",
            context={
                "username": user.username,
                "code": code
            }
        )
