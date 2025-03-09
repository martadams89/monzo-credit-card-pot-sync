import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from app.services.sync_service import SyncService
from app.models.sync_record import SyncRecord
import json

@pytest.fixture
def mock_services():
    monzo_service = MagicMock()
    truelayer_service = MagicMock()
    pot_service = MagicMock()
    setting_repository = MagicMock()
    
    return {
        'monzo_service': monzo_service,
        'truelayer_service': truelayer_service,
        'pot_service': pot_service,
        'setting_repository': setting_repository
    }

@pytest.fixture
def sync_service(mock_services):
    return SyncService(
        mock_services['monzo_service'],
        mock_services['truelayer_service'],
        mock_services['pot_service'],
        mock_services['setting_repository']
    )

def test_sync_disabled_setting(sync_service, mock_services):
    # Setup
    user_id = 1
    mock_services['setting_repository'].get.return_value = json.dumps({'enable_sync': False})
    
    # Execute
    result = sync_service.sync_user_accounts(user_id)
    
    # Assert
    assert result['success'] is False
    assert "Sync is disabled" in result['errors'][0]

def test_successful_sync(sync_service, mock_services, monkeypatch):
    # Setup mocks
    user_id = 1
    mock_services['setting_repository'].get.return_value = json.dumps({'enable_sync': True})
    
    # Mock pot mappings
    mock_services['pot_service'].get_pot_mappings.return_value = {'1': 'pot-123'}
    
    # Mock credit card account
    mock_card = MagicMock()
    mock_card.id = 1
    mock_card.name = "Test Card"
    mock_card.balance = -5000  # -£50.00
    mock_card.last_sync_at = None
    
    # Mock Monzo account
    mock_monzo = MagicMock()
    mock_monzo.id = 2
    
    # Mock pot
    mock_pot = MagicMock()
    mock_pot.id = 'pot-123'
    
    # Mock Account query
    monkeypatch.setattr('app.models.account.Account.query.filter_by', 
                       lambda **kwargs: MagicMock(all=lambda: [mock_card] if 'credit_card' in kwargs.values() else [mock_monzo]))
    
    # Mock DB session
    mock_db_session = MagicMock()
    monkeypatch.setattr('app.services.sync_service.db.session', mock_db_session)
    
    # Mock get_pots
    mock_services['monzo_service'].get_pots.return_value = [mock_pot]
    
    # Mock refresh_account
    mock_services['truelayer_service'].refresh_account.return_value = True
    
    # Execute
    result = sync_service.sync_user_accounts(user_id)
    
    # Assert
    assert result['success'] is True
    assert result['accounts_synced'] == 1
    assert mock_services['monzo_service'].update_pot.called
    assert mock_services['monzo_service'].update_pot.call_args[0][2] == 5000  # £50.00 positive in pot
