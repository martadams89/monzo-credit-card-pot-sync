import os
from time import time
import tempfile
import pytest
from datetime import datetime, timedelta

from app import create_app
from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.domain.auth_providers import (
    AmericanExpressAuthProvider,
    AuthProviderType,
    BarclaycardAuthProvider,
    MonzoAuthProvider,
)
from app.domain.settings import Setting
from app.extensions import db as _db
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.user import User
from werkzeug.security import generate_password_hash


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

    account_repository = SqlAlchemyAccountRepository(_db)
    account_repository.save(monzo_account)
    account_repository.save(amex_account)

    setting_repository = SqlAlchemySettingRepository(_db)
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

    account_repository = SqlAlchemyAccountRepository(_db)
    account_repository.save(monzo_account)
    account_repository.save(amex_account)

    setting_repository = SqlAlchemySettingRepository(_db)
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


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Create a temp file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
        'SECRET_KEY': 'test-key',
        'MONZO_CLIENT_ID': 'test-client-id',
        'MONZO_CLIENT_SECRET': 'test-client-secret',
        'MONZO_REDIRECT_URI': 'http://localhost:8000/auth/callback/monzo',
        'MAIL_DEFAULT_SENDER': 'test@example.com',
        'MAIL_SERVER': 'localhost',
        'MAIL_PORT': 25,
        'MAIL_USE_TLS': False,
        'MAIL_USERNAME': None,
        'MAIL_PASSWORD': None,
    })
    
    # Create the database and tables
    with app.app_context():
        _db.create_all()
    
    yield app
    
    # Close and remove the temp database
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def db(app):
    """Create a database instance for testing."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield _db
        _db.session.remove()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()

@pytest.fixture
def auth(client):
    """Authentication helper for tests."""
    class AuthActions:
        def __init__(self, client):
            self._client = client
        
        def login(self, email='test@example.com', password='password'):
            return self._client.post(
                '/auth/login',
                data={'email': email, 'password': password}
            )
        
        def logout(self):
            return self._client.get('/auth/logout')
    
    return AuthActions(client)

@pytest.fixture
def normal_user(db):
    """Create a normal user for testing."""
    user = User(
        id='user1',
        username='testuser',
        email='test@example.com',
        password_hash=generate_password_hash('password'),
        role='user',
        is_active=True,
        is_email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    user = User(
        id='admin1',
        username='adminuser',
        email='admin@example.com',
        password_hash=generate_password_hash('password'),
        role='admin',
        is_active=True,
        is_email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def logged_in_user(client, normal_user):
    """A logged in user for tests."""
    client.post(
        '/auth/login',
        data={'email': normal_user.email, 'password': 'password'}
    )
    return normal_user

@pytest.fixture
def logged_in_admin(client, admin_user):
    """A logged in admin for tests."""
    client.post(
        '/auth/login',
        data={'email': admin_user.email, 'password': 'password'}
    )
    return admin_user