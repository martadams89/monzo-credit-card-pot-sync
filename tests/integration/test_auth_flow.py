"""Integration tests for authentication flows"""

import pytest
from unittest.mock import patch
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
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False  # Disable CSRF for testing
    })
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def test_registration_login_flow(client):
    """Test the registration and login flow"""
    # Register a new user
    response = client.post('/auth/register', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'password123',
        'password2': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Your account has been created' in response.data
    
    # Login with the new user
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'password123',
        'remember_me': False
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify if user is logged in
    with client.session_transaction() as session:
        assert '_user_id' in session
    
    # Logout
    response = client.get('/auth/logout', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'You have been logged out' in response.data
    
    # Verify user is logged out
    with client.session_transaction() as session:
        assert '_user_id' not in session

@patch('app.auth.routes.AuthService')
def test_two_factor_auth_flow(mock_auth_service, client):
    """Test the two-factor authentication flow"""
    # Create a user with 2FA enabled
    with client.application.app_context():
        user = User(username='tfa_user', email='tfa@example.com')
        user.set_password('password123')
        user.totp_secret = 'testsecret'
        user.totp_enabled = True
        db.session.add(user)
        db.session.commit()
    
    # Mock verify_totp to always return False first for regular login, 
    # then return True for 2FA verification
    instance = mock_auth_service.return_value
    instance.verify_totp.side_effect = [True]
    
    # Login - should redirect to 2FA verification
    response = client.post('/auth/login', data={
        'username': 'tfa_user',
        'password': 'password123',
        'remember_me': False
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Verification Required' in response.data
    
    # Complete 2FA verification
    with client.session_transaction() as session:
        session['user_id'] = user.id
    
    response = client.post('/auth/two-factor/verify', data={
        'code': '123456'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert instance.verify_totp.called
    
    # Verify user is logged in
    with client.session_transaction() as session:
        assert '_user_id' in session
