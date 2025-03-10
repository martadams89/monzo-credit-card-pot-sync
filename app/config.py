import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration for the application."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    DEBUG = False
    TESTING = False
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    
    # Base URL for external connections
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000')
    
    # Monzo API settings
    MONZO_CLIENT_ID = os.environ.get('MONZO_CLIENT_ID')
    MONZO_CLIENT_SECRET = os.environ.get('MONZO_CLIENT_SECRET')
    MONZO_REDIRECT_URI = os.environ.get('MONZO_REDIRECT_URI', f"{BASE_URL}/auth/callback/monzo")
    
    # TrueLayer API settings
    TRUELAYER_CLIENT_ID = os.environ.get('TRUELAYER_CLIENT_ID')
    TRUELAYER_CLIENT_SECRET = os.environ.get('TRUELAYER_CLIENT_SECRET')
    TRUELAYER_REDIRECT_URI = os.environ.get('TRUELAYER_REDIRECT_URI', f"{BASE_URL}/auth/callback/truelayer")
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    
    # Backup settings
    BACKUP_DIRECTORY = os.environ.get('BACKUP_DIRECTORY', 'backups')
    BACKUP_COUNT = int(os.environ.get('BACKUP_COUNT', 5))
    
    # Application settings
    VERSION = '1.0.0'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    NOTIFICATION_EMAILS_ENABLED = os.environ.get('NOTIFICATION_EMAILS_ENABLED', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    
    # Use SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///dev.db'
    
    # Print emails to console instead of sending
    MAIL_DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    DEBUG = True
    
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF protection for testing
    WTF_CSRF_ENABLED = False
    
    # Make password hashing faster for tests
    BCRYPT_LOG_ROUNDS = 4
    
    # Disable emails
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    """Production configuration."""
    
    # Ensure proper secret key is set
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Production-specific settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class based on environment."""
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', 'default')
    return config_dict.get(config_name, config_dict['default'])
