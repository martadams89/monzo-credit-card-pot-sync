"""Tests for the core sync balance functionality"""

import pytest
from unittest.mock import patch, MagicMock
import json
from app.core import sync_balance
from app.services.sync_service import SyncService

@pytest.fixture
def mock_container():
    """Create a mock service container"""
    container = MagicMock()
    
    # Mock services
    container.get.side_effect = lambda service_name: {
        'sync_service': MagicMock(spec=SyncService),
        'metrics_service': MagicMock(),
        'account_service': MagicMock(),
        'history_repository': MagicMock(),
        'setting_repository': MagicMock()
    }.get(service_name, MagicMock())
    
    return container

@patch('app.core.container')
def test_sync_balance_enabled(mock_container_patch, mock_container):
    """Test sync_balance when sync is enabled"""
    # Set up mocks
    mock_container_patch.return_value = mock_container
    mock_settings = mock_container.get('setting_repository')
    mock_settings.get.return_value = 'True'  # enable_sync setting
    
    mock_sync_service = mock_container.get('sync_service')
    mock_sync_service.sync_all_accounts.return_value = {
        'status': 'completed',
        'accounts_processed': [
            {
                'account': 'Test Credit Card',
                'status': 'success',
                'actions': [
                    {
                        'type': 'deposit',
                        'amount': 5000,
                        'reason': 'Card balance increased'
                    }
                ],
                'balance': 10000,
                'pot_balance': 10000
            }
        ]
    }
    
    # Call the function
    result = sync_balance()
    
    # Verify the function executed correctly
    assert result is True
    mock_sync_service.sync_all_accounts.assert_called_once()
    
    # Verify history was saved
    mock_history = mock_container.get('history_repository')
    mock_history.save_sync_history.assert_called_once()
    
    # Verify metrics were updated
    mock_metrics = mock_container.get('metrics_service')
    mock_metrics.record_sync.assert_called_once()

@patch('app.core.container')
def test_sync_balance_disabled(mock_container_patch, mock_container):
    """Test sync_balance when sync is disabled"""
    # Set up mocks
    mock_container_patch.return_value = mock_container
    mock_settings = mock_container.get('setting_repository')
    mock_settings.get.return_value = 'False'  # enable_sync setting
    
    mock_sync_service = mock_container.get('sync_service')
    
    # Call the function
    result = sync_balance()
    
    # Verify the function recognized sync is disabled
    assert result is False
    mock_sync_service.sync_all_accounts.assert_not_called()

@patch('app.core.container')
def test_sync_balance_error_handling(mock_container_patch, mock_container):
    """Test sync_balance handles errors gracefully"""
    # Set up mocks
    mock_container_patch.return_value = mock_container
    mock_settings = mock_container.get('setting_repository')
    mock_settings.get.return_value = 'True'  # enable_sync setting
    
    mock_sync_service = mock_container.get('sync_service')
    mock_sync_service.sync_all_accounts.side_effect = Exception("Test error")
    
    # Call the function
    result = sync_balance()
    
    # Verify the function handled the error
    assert result is False
    mock_sync_service.sync_all_accounts.assert_called_once()
    
    # Verify error was logged in history
    mock_history = mock_container.get('history_repository')
    mock_history.save_sync_history.assert_called_once()
    
    # Check that error data was captured
    history_data = mock_history.save_sync_history.call_args[0][0]
    history_dict = json.loads(history_data)
    assert history_dict['status'] == 'error'
    assert any('Test error' in error.get('error', '') for error in history_dict.get('errors', []))
