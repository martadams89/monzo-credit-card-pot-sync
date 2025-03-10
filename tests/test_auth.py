import pytest
from flask import session, g
from app.models.user import User

def test_register(client, db):
    """Test user registration."""
    # Register a new user
    response = client.post(
        '/auth/register',
        data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!'
        },
        follow_redirects=True
    )
    
    # Check response
    assert response.status_code == 200
    assert b'Registration successful' in response.data
    
    # Verify user was added to the database
    user = User.query.filter_by(email='new@example.com').first()
    assert user is not None
    assert user.username == 'newuser'
    assert not user.is_email_verified  # Email verification should be required

def test_login(client, normal_user):
    """Test user login."""
    # Try logging in with correct credentials
    response = client.post(
        '/auth/login',
        data={
            'email': 'test@example.com',
            'password': 'password'
        },
        follow_redirects=True
    )
    
    # Check response
    assert response.status_code == 200
    assert b'Log Out' in response.data  # Should be logged in now
    
    # Test with wrong password
    response = client.post(
        '/auth/login',
        data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        },
        follow_redirects=True
    )
    
    # Should show error message
    assert b'Invalid email or password' in response.data

def test_logout(client, logged_in_user):
    """Test user logout."""
    # User should be logged in already
    response = client.get('/')
    assert b'Log Out' in response.data
    
    # Log out
    response = client.get('/auth/logout', follow_redirects=True)
    
    # Should be logged out
    assert b'Sign in' in response.data
    assert b'Register' in response.data

def test_password_reset_request(client, normal_user):
    """Test password reset request."""
    response = client.post(
        '/auth/reset-password-request',
        data={'email': 'test@example.com'},
        follow_redirects=True
    )
    
    # Check response
    assert response.status_code == 200
    assert b'Password reset instructions have been sent' in response.data

def test_admin_access(client, logged_in_admin):
    """Test admin access."""
    # Admin should be able to access admin pages
    response = client.get('/admin/')
    assert response.status_code == 200
    assert b'Admin Dashboard' in response.data

def test_normal_user_cannot_access_admin(client, logged_in_user):
    """Test that normal users cannot access admin pages."""
    # Normal user should be redirected from admin pages
    response = client.get('/admin/', follow_redirects=True)
    assert b'You do not have permission' in response.data
