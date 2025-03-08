"""Integration tests for security-related routes"""

import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.models.user import User
import json

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

def test_security_settings_page_requires_login(client):
    """Test security settings page requires authentication"""
    response = client.get('/auth/security', follow_redirects=True)
    assert b'Please log in to access this page' in response.data
    
    # Log in and try again
    login(client)
    response = client.get('/auth/security')
    assert response.status_code == 200
    assert b'Security Settings' in response.data

def test_change_password(client):
    """Test changing password"""
    login(client)
    
    # Change password
    response = client.post('/auth/change-password', data={
        'current_password': 'password123',
        'new_password': 'newpassword123',
        'confirm_password': 'newpassword123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Your password has been updated' in response.data
    
    # Logout
    client.get('/auth/logout', follow_redirects=True)
    
    # Try login with old password - should fail
    response = login(client, password='password123')
    assert b'Invalid username or password' in response.data
    
    # Try login with new password - should succeed
    response = login(client, password='newpassword123')
    assert b'Invalid username or password' not in response.data

@patch('app.auth.routes.AuthService')
def test_email_verification_flow(mock_auth_service, client):
    """Test email verification flow"""
    # Mock the auth service
    auth_instance = MagicMock()
    auth_instance.generate_email_verification_token.return_value = "test_token"
    auth_instance.verify_email.return_value = (True, "Email verified successfully")
    mock_auth_service.return_value = auth_instance
    
    # Login
    login(client)
    
    # Send verification email
    response = client.post('/auth/send-verification-email', follow_redirects=True)
    assert response.status_code == 200
    assert b'Verification email sent' in response.data
    
    # Verify token was generated
    auth_instance.generate_email_verification_token.assert_called_once()
    
    # Simulate email verification with token
    response = client.get('/auth/verify-email/test_token', follow_redirects=True)
    assert response.status_code == 200
    assert b'Email verified successfully' in response.data
    
    # Verify token was checked
    auth_instance.verify_email.assert_called_once_with("test_token")

@patch('app.auth.routes.PasskeyService')
def test_passkey_register_flow(mock_passkey_service, client):
    """Test passkey registration API endpoints"""
    # Mock the passkey service
    service_instance = MagicMock()
    service_instance.start_registration.return_value = '{"challenge": "test_challenge"}'
    service_instance.complete_registration.return_value = (True, "Passkey registered successfully")
    mock_passkey_service.return_value = service_instance
    
    # Login
    login(client)
    
    # Test getting registration options
    response = client.post('/auth/passkeys/register/options', 
                          headers={'Content-Type': 'application/json'})
    assert response.status_code == 200
    assert "challenge" in response.json
    
    # Test verifying registration
    credential_data = {
        "id": "test_id",
        "rawId": "test_rawId",
        "type": "public-key",
        "response": {
            "attestationObject": "test_attestation",
            "clientDataJSON": "test_client_data"
        }
    }
    
    response = client.post('/auth/passkeys/register/verify',
                          data=json.dumps(credential_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['message'] == "Passkey registered successfully"
    
    # Verify service was called correctly
    service_instance.start_registration.assert_called_once()
    service_instance.complete_registration.assert_called_once()

@patch('app.auth.routes.PasskeyService')
def test_passkey_authentication_flow(mock_passkey_service, client):
    """Test passkey authentication API endpoints"""
    # Mock the passkey service
    service_instance = MagicMock()
    service_instance.start_authentication.return_value = '{"challenge": "test_auth_challenge"}'
    service_instance.verify_authentication.return_value = (True, "Authentication successful")
    service_instance.find_user_by_credential_id.return_value = None
    mock_passkey_service.return_value = service_instance
    
    # Test getting authentication options
    response = client.post('/auth/passkeys/authenticate/options', 
                          headers={'Content-Type': 'application/json'})
    assert response.status_code == 200
    assert "challenge" in response.json
    
    # Test verifying authentication - failure case
    credential_data = {
        "id": "test_id",
        "rawId": "test_rawId",
        "type": "public-key",
        "response": {
            "authenticatorData": "test_auth_data",
            "clientDataJSON": "test_client_data",
            "signature": "test_signature"
        }
    }
    
    response = client.post('/auth/passkeys/authenticate/verify',
                          data=json.dumps(credential_data),
                          content_type='application/json')
    
    assert response.status_code == 400
    assert response.json['success'] is False

    # Reset mock for success case
    service_instance.reset_mock()
    service_instance.verify_authentication.side_effect = [
        (False, "test_credential_id"),  # First call returns credential ID
        (True, "Authentication successful")  # Second call (with user) succeeds
    ]
    
    # Create a test user for passkey
    user = User.query.filter_by(username='testuser').first()
    service_instance.find_user_by_credential_id.return_value = user
    
    # Test successful authentication
    response = client.post('/auth/passkeys/authenticate/verify',
                          data=json.dumps(credential_data),
                          content_type='application/json')
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'redirect' in response.json
