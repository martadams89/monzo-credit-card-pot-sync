"""Tests for health check endpoints"""

import pytest
from unittest.mock import patch
from app import create_app
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

@pytest.fixture
def client():
    """Create a test client for the app"""
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test_key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'VERSION': '1.0.0-test'
    })
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def test_health_endpoint(client):
    """Test the health endpoint returns correct status when healthy"""
    response = client.get('/main/health')
    
    assert response.status_code == 200
    data = response.json
    assert data['status'] == 'ok'
    assert data['components']['api']['status'] == 'ok'
    assert data['components']['database']['status'] == 'ok'
    assert data['components']['version'] == '1.0.0-test'
    
    # Check that database check was performed
    assert any(check['name'] == 'database_connection' for check in data['checks'])
    assert any(check['status'] == 'pass' for check in data['checks'])

@patch('app.main.routes.db.session.execute')
def test_health_endpoint_db_failure(mock_execute, client):
    """Test the health endpoint returns error status when database fails"""
    mock_execute.side_effect = SQLAlchemyError("Test database error")
    
    response = client.get('/main/health')
    
    assert response.status_code == 503  # Service Unavailable
    data = response.json
    assert data['status'] == 'error'
    assert data['components']['database']['status'] == 'error'
    
    # Check that database failure was reported
    db_checks = [check for check in data['checks'] if check['name'] == 'database_connection']
    assert len(db_checks) == 1
    assert db_checks[0]['status'] == 'fail'
    assert 'message' in db_checks[0]

def test_readiness_endpoint(client):
    """Test the readiness endpoint"""
    response = client.get('/main/readiness')
    
    assert response.status_code == 200
    assert response.json['status'] == 'ready'

def test_liveness_endpoint(client):
    """Test the liveness endpoint"""
    response = client.get('/main/liveness')
    
    assert response.status_code == 200
    assert response.json['status'] == 'alive'
