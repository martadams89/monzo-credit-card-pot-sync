"""Tests for authentication functionality."""

import pytest
from flask import url_for
from app.models.user import User

def test_login_page(client):
    """Test that login page loads correctly."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Sign In' in response.data

def test_login_success(client, test_user):
    """Test successful login."""
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_login_invalid_credentials(client, test_user):
    """Test login with invalid credentials."""
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'wrongpassword',
    })
    assert response.status_code == 200
    assert b'Invalid email or password' in response.data

def test_logout(authenticated_client):
    """Test logout functionality."""
    response = authenticated_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'Sign In' in response.data

def test_protected_route_redirects_unauthenticated(client):
    """Test that protected routes redirect to login page."""
    response = client.get('/dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b'Sign In' in response.data

def test_register_user(client, db):
    """Test user registration."""
    user_count = User.query.count()
    
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'newpassword123',
        'password2': 'newpassword123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert User.query.count() == user_count + 1
    assert User.query.filter_by(email='new@example.com').first() is not None

def test_register_duplicate_email(client, test_user):
    """Test registration with duplicate email."""
    response = client.post('/register', data={
        'username': 'anotheruser',
        'email': 'test@example.com',  # Same as test_user
        'password': 'password123',
        'password2': 'password123'
    })
    
    assert response.status_code == 200
    assert b'Email address already registered' in response.data
