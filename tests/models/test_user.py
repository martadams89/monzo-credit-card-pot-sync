"""Tests for the User model"""

import json
import pytest
from werkzeug.security import check_password_hash
from app.models.user import User
from datetime import datetime

def test_user_creation():
    """Test creating a user"""
    user = User(
        username="testuser",
        email="test@example.com",
        password="password123",
        is_admin=True
    )
    
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.password_hash is not None
    assert user.is_admin is True
    assert user.email_verified is False
    assert user.email_verification_token is None
    assert user.email_verification_expiry is None
    assert user.totp_secret is None
    assert user.totp_enabled is False
    assert user.backup_codes is None
    assert user.passkeys == '[]'
    assert user.preferences == '{}'
    assert user.registered_at is not None
    assert user.last_login_at is None
    assert user.last_login_ip is None

def test_set_password():
    """Test setting a password"""
    user = User(username="testuser", email="test@example.com")
    user.set_password("password123")
    
    assert user.password_hash is not None
    assert check_password_hash(user.password_hash, "password123") is True
    assert check_password_hash(user.password_hash, "wrongpassword") is False

def test_check_password():
    """Test checking a password"""
    user = User(username="testuser", email="test@example.com")
    user.set_password("password123")
    
    assert user.check_password("password123") is True
    assert user.check_password("wrongpassword") is False

def test_requires_2fa():
    """Test the requires_2fa property"""
    user = User(username="testuser", email="test@example.com")
    
    # Default value
    assert user.requires_2fa is False
    
    # When enabled
    user.totp_enabled = True
    assert user.requires_2fa is True

def test_has_passkeys():
    """Test the has_passkeys property"""
    user = User(username="testuser", email="test@example.com")
    
    # Default value (empty array)
    assert user.has_passkeys is False
    
    # Empty array as string
    user.passkeys = '[]'
    assert user.has_passkeys is False
    
    # With passkeys
    user.passkeys = json.dumps([{"id": "test_id", "public_key": "test_key"}])
    assert user.has_passkeys is True
    
    # Invalid JSON
    user.passkeys = 'invalid_json'
    with pytest.raises(json.JSONDecodeError):
        _ = user.has_passkeys

def test_repr():
    """Test the string representation of the User model"""
    user = User(username="testuser", email="test@example.com")
    assert repr(user) == "<User testuser>"

# Add new tests for the email verification fields
def test_user_email_verification_fields():
    """Test email verification fields on User model"""
    user = User(username="testuser", email="test@example.com")
    
    # Initial state - not verified
    assert user.email_verified is False
    assert user.email_verification_token is None
    assert user.email_verification_expiry is None
    
    # Set verification fields
    from datetime import datetime, timedelta
    expiry = datetime.now() + timedelta(days=1)
    user.email_verification_token = "test_token"
    user.email_verification_expiry = expiry
    
    assert user.email_verification_token == "test_token"
    assert user.email_verification_expiry == expiry

# Add tests for the added TOTP features
def test_user_totp_fields():
    """Test TOTP fields on User model"""
    user = User(username="testuser", email="test@example.com")
    
    # Initial state - TOTP not enabled
    assert user.totp_secret is None
    assert user.totp_enabled is False
    assert user.requires_2fa is False
    
    # Enable TOTP
    user.totp_secret = "JBSWY3DPEHPK3PXP"
    user.totp_enabled = True
    
    assert user.totp_secret == "JBSWY3DPEHPK3PXP"
    assert user.totp_enabled is True
    assert user.requires_2fa is True
