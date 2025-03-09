"""Configuration for integration tests."""

import os
import pytest
import tempfile
from app import create_app
from app.extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """Create app for integration tests."""
    # Create temp file for test database
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
    })
    
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()
    
    # Clean up the database file
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope='function')
def db(app):
    """Create a clean database for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture(scope='function')
def authenticated_client(app, client, test_user):
    """Create authenticated test client."""
    with client.session_transaction() as session:
        # Flask-Login uses the 'user_id' to retrieve the user
        session['user_id'] = test_user.id
        session['_fresh'] = True
    return client
