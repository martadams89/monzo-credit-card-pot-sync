"""Tests for the AuthService"""

import pyotp
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from app.services.auth_service import AuthService
from app.models.user import User

@pytest.fixture
def fake_user():
    """Create a fake user for testing"""
    user = User(username="test_user", email="test@example.com")
    user.id = 1
    user.set_password("password123")
    return user

@pytest.fixture
def auth_service():
    """Create an instance of AuthService for testing"""
    mock_user_repository = MagicMock()
    mock_email_service = MagicMock()
    return AuthService(user_repository=mock_user_repository, email_service=mock_email_service)

def test_generate_email_verification_token(auth_service, fake_user):
    """Test generating a verification token for a user's email"""
    token = auth_service.generate_email_verification_token(fake_user)
    
    assert token is not None
    assert len(token) > 0
    assert fake_user.email_verification_token == token
    assert fake_user.email_verification_expiry is not None
    assert fake_user.email_verification_expiry > datetime.now()
    
    # Verify the repository was called to save the user
    assert auth_service.user_repository.save.called
    auth_service.user_repository.save.assert_called_with(fake_user)

def test_verify_email_valid_token(auth_service, fake_user):
    """Test verifying a valid email token"""
    # Setup user with a token
    token = "valid_token"
    fake_user.email_verification_token = token
    fake_user.email_verification_expiry = datetime.now() + timedelta(hours=1)
    fake_user.email_verified = False
    
    # Mock the user repository to return the fake user
    auth_service.user_repository.find_by_email_token.return_value = fake_user
    
    # Verify the token
    success, message = auth_service.verify_email(token)
    
    assert success is True
    assert "successfully" in message
    assert fake_user.email_verified is True
    assert fake_user.email_verification_token is None
    assert fake_user.email_verification_expiry is None
    assert auth_service.user_repository.save.called

def test_verify_email_expired_token(auth_service, fake_user):
    """Test verifying an expired email token"""
    # Setup user with an expired token
    token = "expired_token"
    fake_user.email_verification_token = token
    fake_user.email_verification_expiry = datetime.now() - timedelta(hours=1)
    fake_user.email_verified = False
    
    # Mock the user repository to return the fake user
    auth_service.user_repository.find_by_email_token.return_value = fake_user
    
    # Verify the token
    success, message = auth_service.verify_email(token)
    
    assert success is False
    assert "expired" in message
    assert fake_user.email_verified is False

def test_verify_email_invalid_token(auth_service):
    """Test verifying an invalid email token"""
    # Mock the user repository to not find any user
    auth_service.user_repository.find_by_email_token.return_value = None
    
    # Verify the token
    success, message = auth_service.verify_email("invalid_token")
    
    assert success is False
    assert "Invalid" in message

def test_generate_totp_secret(auth_service, fake_user):
    """Test generating a TOTP secret for a user"""
    secret = auth_service.generate_totp_secret(fake_user)
    
    assert secret is not None
    assert len(secret) > 0
    assert fake_user.totp_secret == secret
    assert fake_user.totp_enabled is False
    assert auth_service.user_repository.save.called

def test_get_totp_qr_code(auth_service, fake_user):
    """Test generating a QR code for TOTP setup"""
    # User without a TOTP secret
    fake_user.totp_secret = None
    qr_code = auth_service.get_totp_qr_code(fake_user)
    
    assert qr_code is not None
    assert fake_user.totp_secret is not None
    assert auth_service.user_repository.save.called
    
    # Reset mock
    auth_service.user_repository.save.reset_mock()
    
    # User with an existing TOTP secret
    fake_user.totp_secret = "existing_secret"
    qr_code = auth_service.get_totp_qr_code(fake_user)
    
    assert qr_code is not None
    assert not auth_service.user_repository.save.called

def test_verify_totp(auth_service, fake_user):
    """Test verifying a TOTP code"""
    # Setup user with a TOTP secret
    secret = pyotp.random_base32()
    fake_user.totp_secret = secret
    
    # Generate a valid TOTP code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    # Test with valid code
    assert auth_service.verify_totp(fake_user, valid_code) is True
    
    # Test with invalid code
    assert auth_service.verify_totp(fake_user, "123456") is False
    
    # Test with user having no TOTP secret
    fake_user.totp_secret = None
    assert auth_service.verify_totp(fake_user, valid_code) is False

def test_enable_totp(auth_service, fake_user):
    """Test enabling TOTP for a user"""
    # Setup user with a TOTP secret
    secret = pyotp.random_base32()
    fake_user.totp_secret = secret
    fake_user.totp_enabled = False
    
    # Generate a valid TOTP code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    # Test with valid code
    result = auth_service.enable_totp(fake_user, valid_code)
    
    assert result is True
    assert fake_user.totp_enabled is True
    assert auth_service.user_repository.save.called
    
    # Reset mock
    auth_service.user_repository.save.reset_mock()
    
    # Test with invalid code
    fake_user.totp_enabled = False
    result = auth_service.enable_totp(fake_user, "123456")
    
    assert result is False
    assert fake_user.totp_enabled is False
    assert not auth_service.user_repository.save.called

def test_disable_totp(auth_service, fake_user):
    """Test disabling TOTP for a user"""
    # Setup user with TOTP enabled
    fake_user.totp_enabled = True
    
    # Test with correct password
    result = auth_service.disable_totp(fake_user, "password123")
    
    assert result is True
    assert fake_user.totp_enabled is False
    assert auth_service.user_repository.save.called
    
    # Reset mock
    auth_service.user_repository.save.reset_mock()
    
    # Enable TOTP again
    fake_user.totp_enabled = True
    
    # Test with incorrect password
    result = auth_service.disable_totp(fake_user, "wrongpassword")
    
    assert result is False
    assert fake_user.totp_enabled is True
    assert not auth_service.user_repository.save.called

def test_generate_email_code(auth_service, fake_user):
    """Test generating an email verification code"""
    code = auth_service.generate_email_code(fake_user)
    
    assert code is not None
    assert len(code) == 6
    assert code.isdigit()
    
    # Verify it was stored in the service's in-memory storage
    assert fake_user.id in auth_service.verification_codes
    assert auth_service.verification_codes[fake_user.id]['code'] == code
    assert auth_service.verification_codes[fake_user.id]['expiry'] > datetime.now()
    
    # Verify email service was called if provided
    assert auth_service.email_service.send_two_factor_code.called
    auth_service.email_service.send_two_factor_code.assert_called_with(fake_user, code)

def test_verify_email_code(auth_service):
    """Test verifying an email verification code"""
    user_id = 1
    code = "123456"
    expiry = datetime.now() + timedelta(minutes=15)
    
    # Store a valid code
    auth_service.verification_codes[user_id] = {
        'code': code,
        'expiry': expiry
    }
    
    # Test with valid code
    assert auth_service.verify_email_code(user_id, code) is True
    
    # Code should be deleted after successful verification
    assert user_id not in auth_service.verification_codes
    
    # Test with invalid code
    auth_service.verification_codes[user_id] = {
        'code': code,
        'expiry': expiry
    }
    assert auth_service.verify_email_code(user_id, "654321") is False
    
    # Invalid code shouldn't delete the stored code
    assert user_id in auth_service.verification_codes
    
    # Test with expired code
    auth_service.verification_codes[user_id] = {
        'code': code,
        'expiry': datetime.now() - timedelta(minutes=1)
    }
    assert auth_service.verify_email_code(user_id, code) is False
    
    # Expired code should be deleted
    assert user_id not in auth_service.verification_codes
    
    # Test with non-existent code
    assert auth_service.verify_email_code(999, code) is False
