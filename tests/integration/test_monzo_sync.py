import pytest
from unittest.mock import patch, MagicMock
from app.services.sync_service import SyncService

def create_mock_monzo_response(balance=10000):
    """Create a mock Monzo API response."""
    return {
        "balance": balance,
        "currency": "GBP",
        "spend_today": 0,
        "account_number": "12345678",
        "sort_code": "123456"
    }

def create_mock_truelayer_response(balance=-5000):  # Negative for credit card balance
    """Create a mock TrueLayer API response."""
    return {
        "results": [{
            "account": {
                "account_id": "test-account-id",
                "account_type": "CREDIT_CARD",
                "currency": "GBP"
            },
            "balance": {
                "available": balance / 100,  # Convert from pennies
                "current": balance / 100
            }
        }]
    }

@pytest.mark.integration
def test_full_sync_flow(app, client, test_user):
    """Test a full synchronization flow with mocked external services."""
    # Setup mocks
    with patch('app.services.monzo_service.MonzoService.get_account_balance') as mock_monzo_balance, \
         patch('app.services.monzo_service.MonzoService.get_pots') as mock_monzo_pots, \
         patch('app.services.monzo_service.MonzoService.update_pot') as mock_update_pot, \
         patch('app.services.truelayer_service.TrueLayerService.refresh_account') as mock_refresh:
         
        # Configure mocks
        mock_monzo_balance.return_value = create_mock_monzo_response()
        mock_monzo_pots.return_value = [
            {"id": "pot_123", "name": "Credit Card Pot", "balance": 2000}
        ]
        mock_update_pot.return_value = True
        mock_refresh.return_value = create_mock_truelayer_response()
        
        # Login as test user
        client.post('/auth/login', data={
            'username': test_user.username,
            'password': 'password'
        })
        
        # Trigger a sync
        response = client.post('/api/sync/now', json={'force': True})
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify sync results
        assert data['success'] is True
        assert data['accounts_synced'] > 0
        
        # Verify the mocks were called correctly
        mock_refresh.assert_called()
        mock_update_pot.assert_called_with(
            account_mock_param=MagicMock(), 
            pot_id='pot_123',
            amount=5000  # Should be positive amount to cover credit card debt
        )
