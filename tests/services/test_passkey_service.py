"""Tests for the PasskeyService"""

import json
import base64
from unittest.mock import patch, MagicMock
import pytest
from app.services.passkey_service import PasskeyService
from app.models.user import User

@pytest.fixture
def fake_user():
    """Create a fake user for testing"""
    user = User(username="test_user", email="test@example.com")
    user.id = 1
    user.passkeys = '[]'
    return user

@pytest.fixture
def passkey_service():
    """Create an instance of PasskeyService for testing"""
    mock_user_repository = MagicMock()
    return PasskeyService(user_repository=mock_user_repository)

def test_get_rp_id(passkey_service):
    """Test getting Relying Party ID"""
    with patch('app.services.passkey_service.current_app') as mock_app:
        mock_app.config.get.return_value = "myapp.example.com"
        assert passkey_service._get_rp_id() == "myapp.example.com"
        
        mock_app.config.get.return_value = "myapp.example.com:5000"
        assert passkey_service._get_rp_id() == "myapp.example.com"
        
        mock_app.config.get.return_value = None
        assert passkey_service._get_rp_id() == "localhost"

def test_get_origin(passkey_service):
    """Test getting origin for WebAuthn"""
    with patch('app.services.passkey_service.current_app') as mock_app:
        mock_app.config.get.return_value = "myapp.example.com"
        assert passkey_service._get_origin() == "https://myapp.example.com"
        
        mock_app.config.get.return_value = "localhost:5000"
        assert passkey_service._get_origin() == "http://localhost:5000"

@patch('app.services.passkey_service.session')
@patch('app.services.passkey_service.generate_registration_options')
@patch('app.services.passkey_service.options_to_json')
def test_start_registration(mock_options_to_json, mock_generate_options, mock_session, passkey_service, fake_user):
    """Test starting passkey registration"""
    mock_options = MagicMock()
    mock_generate_options.return_value = mock_options
    mock_options_to_json.return_value = '{"mock": "options"}'
    
    result = passkey_service.start_registration(fake_user)
    
    assert mock_generate_options.called
    assert mock_options_to_json.called
    assert mock_session.__setitem__.called
    assert result == '{"mock": "options"}'

@patch('app.services.passkey_service.session')
def test_start_registration_error(mock_session, passkey_service, fake_user):
    """Test error handling in start_registration"""
    mock_session.__getitem__.side_effect = Exception("Test error")
    
    result = passkey_service.start_registration(fake_user)
    
    assert result is None

@patch('app.services.passkey_service.session')
@patch('app.services.passkey_service.verify_registration_response')
def test_complete_registration(mock_verify, mock_session, passkey_service, fake_user):
    """Test completing passkey registration"""
    mock_session.pop.return_value = base64.b64encode(b'challenge')
    
    # Create mock verification response
    mock_verification = MagicMock()
    mock_verification.credential_id = b'credential_id'
    mock_verification.credential_public_key = b'credential_key'
    mock_verification.credential_device_time = "2023-01-01T12:00:00Z"
    mock_verify.return_value = mock_verification
    
    # Mock the credential data
    credential_data = {
        "id": "test_id",
        "rawId": "test_raw_id",
        "type": "public-key",
        "response": {
            "attestationObject": "test_attestation_object",
            "clientDataJSON": "test_client_data"
        }
    }
    
    success, message = passkey_service.complete_registration(fake_user, credential_data)
    
    assert success is True
    assert "registered successfully" in message
    assert mock_verify.called
    
    # Check passkeys was updated
    passkeys = json.loads(fake_user.passkeys)
    assert len(passkeys) == 1
    assert "id" in passkeys[0]
    assert "public_key" in passkeys[0]
    assert "name" in passkeys[0]

@patch('app.services.passkey_service.session')
def test_complete_registration_no_challenge(mock_session, passkey_service, fake_user):
    """Test error handling when challenge is missing"""
    mock_session.pop.return_value = ''
    
    success, message = passkey_service.complete_registration(fake_user, {})
    
    assert success is False
    assert "challenge not found" in message.lower()

def test_find_user_by_credential_id(passkey_service):
    """Test finding a user by credential ID"""
    # Create mock users and passkeys
    user1 = User(username="user1", email="user1@example.com")
    user1.id = 1
    user1.passkeys = json.dumps([{"id": "cred1", "public_key": "key1"}])
    
    user2 = User(username="user2", email="user2@example.com")
    user2.id = 2
    user2.passkeys = json.dumps([{"id": "cred2", "public_key": "key2"}])
    
    # Set up mock repository
    passkey_service.user_repository.get_all.return_value = [user1, user2]
    
    # Test finding user1
    found_user = passkey_service.find_user_by_credential_id("cred1")
    assert found_user == user1
    
    # Test finding user2
    found_user = passkey_service.find_user_by_credential_id("cred2")
    assert found_user == user2
    
    # Test finding non-existent user
    found_user = passkey_service.find_user_by_credential_id("cred3")
    assert found_user is None

def test_delete_passkey(passkey_service, fake_user):
    """Test deleting a passkey"""
    # Add a passkey to user
    fake_user.passkeys = json.dumps([{
        "id": "test_cred",
        "public_key": "test_key",
        "name": "Test Passkey"
    }])
    
    success, message = passkey_service.delete_passkey(fake_user, "test_cred")
    
    assert success is True
    assert "deleted successfully" in message
    assert fake_user.passkeys == "[]"

def test_delete_nonexistent_passkey(passkey_service, fake_user):
    """Test deleting a passkey that doesn't exist"""
    fake_user.passkeys = json.dumps([{
        "id": "test_cred",
        "public_key": "test_key",
        "name": "Test Passkey"
    }])
    
    success, message = passkey_service.delete_passkey(fake_user, "nonexistent")
    
    assert success is False
    assert "not found" in message
    # Passkey should still be there
    assert len(json.loads(fake_user.passkeys)) == 1

@patch('app.services.passkey_service.session')
@patch('app.services.passkey_service.generate_authentication_options')
@patch('app.services.passkey_service.options_to_json')
def test_start_authentication(mock_options_to_json, mock_generate_options, mock_session, passkey_service):
    """Test starting passkey authentication"""
    mock_options = MagicMock()
    mock_generate_options.return_value = mock_options
    mock_options_to_json.return_value = '{"mock": "auth_options"}'
    
    result = passkey_service.start_authentication()
    
    assert mock_generate_options.called
    assert mock_options_to_json.called
    assert mock_session.__setitem__.called
    assert result == '{"mock": "auth_options"}'
    
    # Test with allow_credentials
    mock_options_to_json.return_value = '{"mock": "auth_options_with_creds"}'
    result = passkey_service.start_authentication(allow_credentials=[{"id": "test_id"}])
    
    assert mock_generate_options.call_count == 2
    assert result == '{"mock": "auth_options_with_creds"}'

@patch('app.services.passkey_service.session')
@patch('app.services.passkey_service.verify_authentication_response')
def test_verify_authentication(mock_verify, mock_session, passkey_service, fake_user):
    """Test verifying a passkey authentication"""
    mock_session.pop.return_value = base64.b64encode(b'auth_challenge')
    
    # Create mock verification response
    mock_verification = MagicMock()
    mock_verification.credential_id = b'credential_id'
    mock_verify.return_value = mock_verification
    
    # Prepare passkeys for the user
    fake_user.passkeys = json.dumps([{
        "id": base64.b64encode(b'credential_id').decode('utf-8'),
        "public_key": base64.b64encode(b'public_key').decode('utf-8'),
        "name": "Test Passkey"
    }])
    
    # Mock the credential data
    credential_data = {
        "id": base64.b64encode(b'credential_id').decode('utf-8'),
        "rawId": "test_raw_id",
        "type": "public-key",
        "response": {
            "authenticatorData": "test_auth_data",
            "clientDataJSON": "test_client_data",
            "signature": "test_signature"
        }
    }
    
    # Test with user provided
    success, message = passkey_service.verify_authentication(credential_data, fake_user)
    
    assert success is True
    assert message == "Authentication successful"
    assert mock_verify.called
    
    # Reset mock
    mock_verify.reset_mock()
    mock_session.pop.return_value = base64.b64encode(b'auth_challenge')
    
    # Test without user (should return credential ID)
    success, credential_id = passkey_service.verify_authentication(credential_data)
    
    assert success is False
    assert credential_id == base64.b64encode(b'credential_id').decode('utf-8')
    assert not mock_verify.called
