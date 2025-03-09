"""Tests for the Cooldown model"""

import pytest
from datetime import datetime, timedelta
from app.models.cooldown import Cooldown

def test_cooldown_creation():
    """Test creating a cooldown instance"""
    account_id = "acc123"
    user_id = 1
    expires_at = datetime.utcnow() + timedelta(hours=3)
    initial_balance = 5000
    
    cooldown = Cooldown(account_id, user_id, expires_at, initial_balance)
    
    assert cooldown.account_id == account_id
    assert cooldown.user_id == user_id
    assert cooldown.expires_at == expires_at
    assert cooldown.initial_balance == initial_balance
    assert cooldown.started_at is not None

def test_cooldown_is_expired_true():
    """Test checking if cooldown is expired (true case)"""
    # Create cooldown with expiry in the past
    expires_at = datetime.utcnow() - timedelta(minutes=5)
    cooldown = Cooldown("acc123", 1, expires_at)
    
    assert cooldown.is_expired() is True

def test_cooldown_is_expired_false():
    """Test checking if cooldown is expired (false case)"""
    # Create cooldown with expiry in the future
    expires_at = datetime.utcnow() + timedelta(hours=1)
    cooldown = Cooldown("acc123", 1, expires_at)
    
    assert cooldown.is_expired() is False

def test_cooldown_repr():
    """Test string representation of Cooldown"""
    expires_at = datetime.utcnow() + timedelta(hours=1)
    cooldown = Cooldown("acc123", 1, expires_at)
    
    repr_str = repr(cooldown)
    assert "Cooldown acc123" in repr_str
    assert "expires_at" in repr_str
    
def test_cooldown_defaults():
    """Test cooldown default values"""
    account_id = "acc123"
    user_id = 1
    expires_at = datetime.utcnow() + timedelta(hours=3)
    
    cooldown = Cooldown(account_id, user_id, expires_at)
    
    assert cooldown.account_id == account_id
    assert cooldown.user_id == user_id
    assert cooldown.expires_at == expires_at
    assert cooldown.initial_balance is None
    assert cooldown.started_at is not None
