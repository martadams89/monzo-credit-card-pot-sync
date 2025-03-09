import os
from time import time

import pytest

from app import create_app
from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.domain.auth_providers import (
    AmericanExpressAuthProvider,
    AuthProviderType,
    BarclaycardAuthProvider,
    MonzoAuthProvider,
)
from app.domain.settings import Setting
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository


class MockDatabase:
    def __init__(self):
        self.session = None


@pytest.fixture
def monzo_provider():
    return MonzoAuthProvider()


@pytest.fixture
def amex_provider():
    return AmericanExpressAuthProvider()


@pytest.fixture
def setting_repository(mocker):
    repository = SqlAlchemySettingRepository(MockDatabase())
    mocker.patch.object(repository, "get", return_value="setting_value")
    mocker.patch("app.domain.auth_providers.repository", repository)
    return repository


@pytest.fixture(scope="function")
def test_client():
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "testing",
    }
    flask_app = create_app(test_config)

    with flask_app.test_client() as testing_client:
        with flask_app.app_context():
            yield testing_client


@pytest.fixture(scope="function")
def seed_data():
    from time import time
    from app.domain.accounts import MonzoAccount
    # Update seed data with pot_id provided
    monzo_account = MonzoAccount("access_token", "refresh_token", int(time()) + 1000, pot_id="default_pot")
    amex_account = TrueLayerAccount(
        AuthProviderType.AMEX.value,
        "access_token",
        "refresh_token",
        time() + 10000,
        "pot_id",
    )

    account_repository = SqlAlchemyAccountRepository(db)
    account_repository.save(monzo_account)
    account_repository.save(amex_account)

    setting_repository = SqlAlchemySettingRepository(db)
    setting_repository.save(Setting("monzo_client_id", "monzo_dummy_client_id"))
    setting_repository.save(Setting("monzo_client_secret", "monzo_dummy_client_secret"))
    setting_repository.save(
        Setting("truelayer_client_id", os.getenv("TRUELAYER_SANDBOX_CLIENT_ID"))
    )
    setting_repository.save(
        Setting("truelayer_client_secret", os.getenv("TRUELAYER_SANDBOX_CLIENT_SECRET"))
    )


@pytest.fixture(scope="function")
def seed_data_joint():
    monzo_account = MonzoAccount(
        "access_token", "refresh_token", time() + 10000, "pot_id", account_id="joint_123"
    )
    amex_account = TrueLayerAccount(
        AuthProviderType.AMEX.value,
        "access_token",
        "refresh_token",
        time() + 10000,
        "pot_id",
    )

    account_repository = SqlAlchemyAccountRepository(db)
    account_repository.save(monzo_account)
    account_repository.save(amex_account)

    setting_repository = SqlAlchemySettingRepository(db)
    setting_repository.save(Setting("monzo_client_id", "monzo_dummy_client_id"))
    setting_repository.save(Setting("monzo_client_secret", "monzo_dummy_client_secret"))
    setting_repository.save(
        Setting("truelayer_client_id", os.getenv("TRUELAYER_SANDBOX_CLIENT_ID"))
    )
    setting_repository.save(
        Setting("truelayer_client_secret", os.getenv("TRUELAYER_SANDBOX_CLIENT_SECRET"))
    )


@pytest.fixture()
def barclaycard_sandbox_provider(mocker):
    barclaycard_provider = BarclaycardAuthProvider()
    barclaycard_provider.api_url = "https://api.truelayer-sandbox.com"
    barclaycard_provider.auth_url = "https://auth.truelayer-sandbox.com"
    barclaycard_provider.token_url = "https://auth.truelayer-sandbox.com"
    mocker.patch.object(
        barclaycard_provider,
        "get_provider_specific_oauth_request_params",
        return_value={
            "providers": "uk-cs-mock",
            "scope": barclaycard_provider.oauth_scopes,
        },
    )

    replaced_provider_mapping = {AuthProviderType.BARCLAYCARD: barclaycard_provider}
    mocker.patch("app.web.auth.provider_mapping", replaced_provider_mapping)
    return barclaycard_provider


"""Global test fixtures"""

import pytest
from unittest.mock import MagicMock
from app.utils.json_utils import dumps

@pytest.fixture(autouse=True)
def mock_sync_history_repository(monkeypatch):
    """Mock sync history repository to handle datetime serialization"""
    mock_repo = MagicMock()
    
    def mock_save_sync_result(data):
        """Mock implementation that properly serializes datetime objects"""
        # Convert to JSON string and back to ensure serializability
        json_data = dumps(data)
        return True
        
    mock_repo.save_sync_result.side_effect = mock_save_sync_result
    monkeypatch.setattr('app.core.history_repository', mock_repo)
    return mock_repo

"""Test fixtures for pytest."""

import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.account import Account
import os

@pytest.fixture(scope='session')
def app():
    """Create and configure a Flask app for testing."""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-key',
    })
    
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def db(app):
    """Create a fresh database for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the app."""
    return app.test_client()

@pytest.fixture(scope='function')
def test_user(db):
    """Create a test user."""
    user = User(
        username='testuser',
        email='test@example.com',
        is_active=True
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture(scope='function')
def admin_user(db):
    """Create an admin user."""
    user = User(
        username='adminuser',
        email='admin@example.com',
        is_active=True,
        is_admin=True
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user

"""Configuration for pytest tests."""

import os
import pytest
import tempfile
from datetime import datetime
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.account import Account
from app.models.sync_record import SyncRecord
from app.models.setting import Setting

@pytest.fixture(scope='session')
def app():
    """Create Flask app for testing."""
    # Create temp file for test database
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with test config
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'MAIL_SUPPRESS_SEND': True,
        'RATELIMIT_ENABLED': False,
    })
    
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.session.remove()
        _db.drop_all()
    
    # Clean up the database file
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope='function')
def db(app):
    """Create clean database for each test."""
    with app.app_context():
        _db.session.begin_nested()
        yield _db
        _db.session.rollback()

@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture(scope='function')
def test_user(db):
    """Create test user."""
    user = User(
        username='testuser',
        email='test@example.com',
        is_active=True,
        created_at=datetime.utcnow()
    )
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture(scope='function')
def admin_user(db):
    """Create admin user."""
    user = User(
        username='admin',
        email='admin@example.com',
        is_active=True,
        is_admin=True,
        created_at=datetime.utcnow()
    )
    user.set_password('adminpass')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture(scope='function')
def authenticated_client(app, client, test_user):
    """Create authenticated test client."""
    with client.session_transaction() as session:
        # Flask-Login uses the 'user_id' to retrieve the user
        session['user_id'] = test_user.id
        session['_fresh'] = True
    return client

@pytest.fixture(scope='function')
def admin_client(app, client, admin_user):
    """Create authenticated admin client."""
    with client.session_transaction() as session:
        session['user_id'] = admin_user.id
        session['_fresh'] = True
    return client

@pytest.fixture(scope='function')
def test_account(db, test_user):
    """Create test account."""
    account = Account(
        user_id=test_user.id,
        account_id='acc_123456',
        name='Test Credit Card',
        type='credit_card',
        provider='test_provider',
        created_at=datetime.utcnow()
    )
    db.session.add(account)
    db.session.commit()
    return account

@pytest.fixture(scope='function')
def test_monzo_account(db, test_user):
    """Create test Monzo account."""
    account = Account(
        user_id=test_user.id,
        account_id='acc_monzo123',
        name='Test Monzo Account',
        type='monzo',
        provider='monzo',
        created_at=datetime.utcnow()
    )
    db.session.add(account)
    db.session.commit()
    return account

@pytest.fixture(scope='function')
def test_settings(db):
    """Create test settings."""
    settings = [
        Setting(key='test_setting', value='test_value'),
        Setting(key='sync_interval', value='15'),
        Setting(key='enable_sync', value='true'),
    ]
    db.session.bulk_save_objects(settings)
    db.session.commit()
    return settings