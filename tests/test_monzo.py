import pytest
import json
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app.models.monzo import MonzoAccount, ManzoPot

@pytest.fixture
def mock_monzo_api():
    """Create a mock for the MonzoAPIService."""
    with patch('app.services.monzo_api.MonzoAPIService') as mock:
        instance = mock.return_value
        
        # Set up mock responses
        instance.get_auth_url.return_value = "https://auth.monzo.com/?client_id=test&redirect_uri=test&response_type=code&state=test"
        
        instance.exchange_code_for_tokens.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600
        }
        
        instance.get_account_details.return_value = {
            'id': 'acc_12345',
            'description': 'Test Monzo Account'
        }
        
        instance.get_pots.return_value = [
            {
                'id': 'pot_12345',
                'name': 'Test Pot',
                'balance': 10000,
                'currency': 'GBP',
                'deleted': False
            }
        ]
        
        instance.get_balance.return_value = {
            'balance': 8000,
            'currency': 'GBP'
        }
        
        yield instance

@pytest.fixture
def monzo_account(db, normal_user):
    """Create a test Monzo account."""
    account = MonzoAccount(
        id=str(uuid.uuid4()),
        user_id=normal_user.id,
        name='Test Monzo Account',
        type='monzo',
        account_id='acc_12345',
        access_token='test_access_token',
        refresh_token='test_refresh_token',
        token_expires_at=datetime.utcnow() + timedelta(hours=1),
        balance=8000,
        currency='GBP',
        is_active=True,
        sync_enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(account)
    
    # Add a pot for this account
    pot = ManzoPot(
        id=str(uuid.uuid4()),
        account_id=account.id,
        name='Test Pot',
        pot_id='pot_12345',
        balance=10000,
        currency='GBP',
        is_locked=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(pot)
    
    db.session.commit()
    return account

def test_monzo_dashboard_requires_login(client):
    """Test that Monzo dashboard page requires login."""
    response = client.get('/monzo/', follow_redirects=True)
    assert b'Sign in' in response.data
    assert b'Please log in to access this page' in response.data

def test_monzo_dashboard_shows_accounts(client, logged_in_user, monzo_account):
    """Test that Monzo dashboard shows accounts for logged in user."""
    response = client.get('/monzo/')
    assert response.status_code == 200
    assert b'Test Monzo Account' in response.data
    assert b'Test Pot' in response.data

def test_add_account_page(client, logged_in_user, mock_monzo_api):
    """Test the add account page."""
    response = client.get('/monzo/add-account')
    assert response.status_code == 200
    assert b'Add Monzo Account' in response.data
    assert b'Connect Monzo Account' in response.data

@patch('app.web.monzo.MonzoAPIService')
def test_auth_callback_success(mock_monzo_api_class, client, logged_in_user, db):
    """Test successful OAuth callback handling."""
    # Setup mock
    mock_instance = mock_monzo_api_class.return_value
    mock_instance.exchange_code_for_tokens.return_value = {
        'access_token': 'new_access_token',
        'refresh_token': 'new_refresh_token',
        'expires_in': 3600
    }
    mock_instance.get_account_details.return_value = {
        'id': 'acc_67890',
        'description': 'New Monzo Account'
    }
    mock_instance.get_pots.return_value = []
    
    # Set up session state
    with client.session_transaction() as session:
        session['monzo_auth_state'] = 'test_state'
    
    # Test the callback
    response = client.get('/monzo/callback?code=test_code&state=test_state', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Monzo account connected successfully' in response.data
    
    # Verify new account was added
    new_account = MonzoAccount.query.filter_by(account_id='acc_67890').first()
    assert new_account is not None
    assert new_account.user_id == logged_in_user.id
