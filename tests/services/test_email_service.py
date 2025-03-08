"""Tests for the EmailService"""

from unittest.mock import patch, MagicMock
import pytest
from app.services.email_service import EmailService
from app.models.user import User

@pytest.fixture
def fake_user():
    """Create a fake user for testing"""
    return User(username="test_user", email="test@example.com")

@pytest.fixture
def email_service():
    """Create an instance of EmailService for testing"""
    mock_settings_repository = MagicMock()
    
    # Configure mock settings
    def get_setting(key, default=None):
        settings = {
            "email_smtp_server": "smtp.example.com",
            "email_smtp_port": "587",
            "email_smtp_username": "test@example.com",
            "email_smtp_password": "password123",
            "email_from_address": "noreply@example.com",
            "email_use_tls": "True"
        }
        return settings.get(key, default)
    
    mock_settings_repository.get.side_effect = get_setting
    
    return EmailService(settings_repository=mock_settings_repository)

@patch('app.services.email_service.smtplib.SMTP')
def test_send_email_with_tls(mock_smtp, email_service):
    """Test sending an email with TLS enabled"""
    # Setup mock
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
    
    # Call the method
    result = email_service.send_email(
        recipient="recipient@example.com",
        subject="Test Subject",
        template_name="email_verification",
        context={"username": "test_user", "verification_link": "http://example.com/verify"}
    )
    
    # Verify result
    assert result is True
    
    # Verify SMTP calls
    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("test@example.com", "password123")
    mock_smtp_instance.sendmail.assert_called_once()

@patch('app.services.email_service.smtplib.SMTP')
def test_send_email_without_tls(mock_smtp, email_service):
    """Test sending an email without TLS"""
    # Modify email_use_tls setting
    email_service.settings_repository.get.side_effect = lambda key, default=None: {
        "email_smtp_server": "smtp.example.com",
        "email_smtp_port": "587", 
        "email_smtp_username": "test@example.com",
        "email_smtp_password": "password123",
        "email_from_address": "noreply@example.com",
        "email_use_tls": "False"
    }.get(key, default)
    
    # Setup mock
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
    
    # Call the method
    result = email_service.send_email(
        recipient="recipient@example.com",
        subject="Test Subject",
        template_name="email_verification",
        context={"username": "test_user", "verification_link": "http://example.com/verify"}
    )
    
    # Verify result
    assert result is True
    
    # Verify SMTP calls
    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_smtp_instance.starttls.assert_not_called()
    mock_smtp_instance.login.assert_called_once_with("test@example.com", "password123")
    mock_smtp_instance.sendmail.assert_called_once()

@patch('app.services.email_service.smtplib.SMTP')
def test_send_email_missing_config(mock_smtp, email_service):
    """Test sending an email with missing configuration"""
    # Remove a required config
    email_service.settings_repository.get.side_effect = lambda key, default=None: {
        "email_smtp_server": "",  # Empty server
        "email_smtp_port": "587",
        "email_smtp_username": "test@example.com",
        "email_smtp_password": "password123",
        "email_from_address": "noreply@example.com",
        "email_use_tls": "True"
    }.get(key, default)
    
    # Call the method
    result = email_service.send_email(
        recipient="recipient@example.com",
        subject="Test Subject",
        template_name="email_verification",
        context={"username": "test_user", "verification_link": "http://example.com/verify"}
    )
    
    # Verify result
    assert result is False
    
    # Verify SMTP calls
    mock_smtp.assert_not_called()

def test_send_verification_email(email_service, fake_user):
    """Test sending a verification email"""
    with patch.object(email_service, 'send_email', return_value=True) as mock_send_email:
        result = email_service.send_verification_email(
            fake_user,
            "http://example.com/verify"
        )
        
        assert result is True
        mock_send_email.assert_called_once_with(
            recipient=fake_user.email,
            subject="Verify Your Email - Monzo Credit Card Pot Sync",
            template_name="email_verification",
            context={
                "username": fake_user.username,
                "verification_link": "http://example.com/verify"
            }
        )

def test_send_password_reset_email(email_service, fake_user):
    """Test sending a password reset email"""
    with patch.object(email_service, 'send_email', return_value=True) as mock_send_email:
        result = email_service.send_password_reset_email(
            fake_user,
            "http://example.com/reset"
        )
        
        assert result is True
        mock_send_email.assert_called_once_with(
            recipient=fake_user.email,
            subject="Reset Your Password - Monzo Credit Card Pot Sync",
            template_name="password_reset",
            context={
                "username": fake_user.username,
                "reset_link": "http://example.com/reset"
            }
        )

def test_send_two_factor_code(email_service, fake_user):
    """Test sending a two-factor authentication code"""
    with patch.object(email_service, 'send_email', return_value=True) as mock_send_email:
        result = email_service.send_two_factor_code(
            fake_user,
            "123456"
        )
        
        assert result is True
        mock_send_email.assert_called_once_with(
            recipient=fake_user.email,
            subject="Your Login Verification Code - Monzo Credit Card Pot Sync",
            template_name="two_factor_code",
            context={
                "username": fake_user.username,
                "code": "123456"
            }
        )
