"""Tests for two-factor authentication functionality"""

import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.models.user import User

@pytest.fixture
def client():
    """Create a test client for the app"""
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test_key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False  # Disable CSRF for testing
    })
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Create test user
            user = User(username='testuser', email='test@example.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            
            yield client
            db.session.remove()
            db.drop_all()

def login(client, username='testuser', password='password123'):
    """Helper to log in a user"""
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)

@patch('app.auth.routes.AuthService')
def test_two_factor_setup_flow(mock_auth_service, client):
    """Test the two-factor setup process"""
    # Mock the auth service
    auth_instance = MagicMock()
    auth_instance.generate_totp_secret.return_value = "JBSWY3DPEHPK3PXP"
    auth_instance.get_totp_qr_code.return_value = "base64_encoded_qr_code"
    auth_instance.enable_totp.return_value = True
    mock_auth_service.return_value = auth_instance
    
    # Login
    login(client)
    
    # Visit the setup page
    response = client.get('/auth/two-factor/setup')
    assert response.status_code == 200
    assert b'Set Up Two-Factor Authentication' in response.data
    
    # Setup should generate a secret and QR code
    auth_instance.get_totp_qr_code.assert_called_once()
    
    # Verify setup with correct code
    response = client.post('/auth/two-factor/setup', data={
        'verification_code': '123456'  # Code doesn't matter as we mock the verification
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Two-factor authentication has been enabled' in response.data
    auth_instance.enable_totp.assert_called_once_with(MagicMock(), '123456')

@patch('app.auth.routes.AuthService')
def test_disable_two_factor(mock_auth_service, client):
    """Test disabling two-factor authentication"""
    # Mock the auth service
    auth_instance = MagicMock()
    auth_instance.disable_totp.return_value = True
    mock_auth_service.return_value = auth_instance
    
    # Login
    login(client)
    
    # Disable 2FA
    response = client.post('/auth/disable-two-factor', data={
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Two-factor authentication has been disabled' in response.data
    auth_instance.disable_totp.assert_called_once()
    
    # Test with wrong password
    auth_instance.disable_totp.reset_mock()
    auth_instance.disable_totp.return_value = False
    
    response = client.post('/auth/disable-two-factor', data={
        'password': 'wrong_password'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Incorrect password' in response.data
    auth_instance.disable_totp.assert_called_once()
