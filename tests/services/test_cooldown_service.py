"""Tests for the CooldownService"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from app.services.cooldown_service import CooldownService
from app.models.cooldown import Cooldown

@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = MagicMock()
    return session

@pytest.fixture
def cooldown_service(mock_db_session):
    """Create a CooldownService with mocked dependencies"""
    return CooldownService(mock_db_session)

def test_start_cooldown(cooldown_service):
    """Test starting a cooldown period"""
    with patch('app.services.cooldown_service.Cooldown') as mock_cooldown:
        # Setup
        mock_instance = MagicMock()
        mock_cooldown.return_value = mock_instance
        
        # Execute
        result = cooldown_service.start_cooldown('acc123', 1, 3, 5000)
        
        # Assert
        assert result == mock_instance
        mock_cooldown.assert_called_once()
        assert mock_cooldown.call_args[1]['account_id'] == 'acc123'
        assert mock_cooldown.call_args[1]['user_id'] == 1
        assert mock_cooldown.call_args[1]['initial_balance'] == 5000
        
        # Check that expiry time is approximately 3 hours in the future
        expires_at = mock_cooldown.call_args[1]['expires_at']
        now = datetime.utcnow()
        delta = expires_at - now
        assert 2.9 <= delta.total_seconds() / 3600 <= 3.1  # within 6 minutes of 3 hours

def test_start_cooldown_exception(cooldown_service):
    """Test exception handling when starting a cooldown period"""
    with patch('app.services.cooldown_service.Cooldown') as mock_cooldown:
        # Setup to raise exception
        mock_cooldown.side_effect = Exception("Test exception")
        
        # Execute
        result = cooldown_service.start_cooldown('acc123', 1, 3)
        
        # Assert
        assert result is None
        cooldown_service.db.session.rollback.assert_called_once()

def test_get_active_cooldown(cooldown_service):
    """Test getting an active cooldown"""
    with patch('app.services.cooldown_service.Cooldown.query') as mock_query:
        # Setup mock query chain
        mock_filter_by = MagicMock()
        mock_filter = MagicMock()
        mock_order_by = MagicMock()
        mock_first = MagicMock()
        
        mock_query.filter_by.return_value = mock_filter_by
        mock_filter_by.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.first.return_value = "active_cooldown"
        
        # Execute
        result = cooldown_service.get_active_cooldown('acc123', 1)
        
        # Assert
        assert result == "active_cooldown"
        mock_query.filter_by.assert_called_once_with(account_id='acc123', user_id=1)

def test_is_in_cooldown_true(cooldown_service):
    """Test checking if account is in cooldown (true case)"""
    with patch.object(cooldown_service, 'get_active_cooldown', return_value=MagicMock()) as mock_get:
        # Execute
        result = cooldown_service.is_in_cooldown('acc123', 1)
        
        # Assert
        assert result is True
        mock_get.assert_called_once_with('acc123', 1)

def test_is_in_cooldown_false(cooldown_service):
    """Test checking if account is in cooldown (false case)"""
    with patch.object(cooldown_service, 'get_active_cooldown', return_value=None) as mock_get:
        # Execute
        result = cooldown_service.is_in_cooldown('acc123', 1)
        
        # Assert
        assert result is False
        mock_get.assert_called_once_with('acc123', 1)

def test_get_remaining_time(cooldown_service):
    """Test getting remaining cooldown time"""
    future = datetime.utcnow() + timedelta(hours=1, minutes=30)
    mock_cooldown = MagicMock()
    mock_cooldown.expires_at = future
    
    with patch.object(cooldown_service, 'get_active_cooldown', return_value=mock_cooldown) as mock_get:
        # Execute
        result = cooldown_service.get_remaining_time('acc123', 1)
        
        # Assert
        assert 5350 <= result <= 5450  # ~5400 seconds (1h30m)
        mock_get.assert_called_once_with('acc123', 1)

def test_get_remaining_time_no_cooldown(cooldown_service):
    """Test getting remaining time when no cooldown exists"""
    with patch.object(cooldown_service, 'get_active_cooldown', return_value=None) as mock_get:
        # Execute
        result = cooldown_service.get_remaining_time('acc123', 1)
        
        # Assert
        assert result == 0
        mock_get.assert_called_once_with('acc123', 1)

def test_clear_cooldown(cooldown_service):
    """Test clearing cooldown"""
    with patch('app.services.cooldown_service.Cooldown.query') as mock_query:
        # Setup mock query
        mock_filter_by1 = MagicMock()
        mock_filter_by2 = MagicMock()
        mock_delete = MagicMock(return_value=2)
        
        mock_query.filter_by.return_value = mock_filter_by1
        mock_filter_by1.filter_by.return_value = mock_filter_by2
        mock_filter_by2.delete = mock_delete
        
        # Execute
        result = cooldown_service.clear_cooldown(account_id='acc123', user_id=1)
        
        # Assert
        assert result == 2
        cooldown_service.db.session.commit.assert_called_once()
