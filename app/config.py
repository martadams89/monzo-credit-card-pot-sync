"""Configuration for the application."""

import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask-Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', 'yes', '1')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    
    # Monzo API
    MONZO_CLIENT_ID = os.environ.get('MONZO_CLIENT_ID')
    MONZO_CLIENT_SECRET = os.environ.get('MONZO_CLIENT_SECRET')
    MONZO_REDIRECT_URI = os.environ.get('MONZO_REDIRECT_URI')
    
    # TrueLayer API
    TRUELAYER_CLIENT_ID = os.environ.get('TRUELAYER_CLIENT_ID')
    TRUELAYER_CLIENT_SECRET = os.environ.get('TRUELAYER_CLIENT_SECRET')
    TRUELAYER_REDIRECT_URI = os.environ.get('TRUELAYER_REDIRECT_URI')
    
    # Logging
    LOG_DIR = os.environ.get('LOG_DIR', 'logs')
    LOG_FILE = os.environ.get('LOG_FILE', os.path.join(LOG_DIR, 'app.log'))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Application settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    UPLOAD_FOLDER = 'uploads'
    
    # Registration and security
    ALLOW_REGISTRATION = os.environ.get('ALLOW_REGISTRATION', 'true').lower() in ('true', 'yes', '1')
    PASSWORD_MIN_LENGTH = int(os.environ.get('PASSWORD_MIN_LENGTH', 8))
    ENABLE_2FA = os.environ.get('ENABLE_2FA', 'false').lower() in ('true', 'yes', '1')
    
    # Application URLs
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day, 50 per hour')
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    
    # Development options
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = 'DEBUG'
    
    # Development SQLAlchemy settings
    SQLALCHEMY_ECHO = True
    
    # Development mail settings
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ('true', 'yes', '1')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    LOG_LEVEL = 'DEBUG'
    MAIL_SUPPRESS_SEND = True
    
    # Faster password hashing for tests
    SECURITY_PASSWORD_HASH = 'plaintext'
    
    # Disable rate limiting
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'ERROR')
    
    # Production security
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('WTF_CSRF_TIME_LIMIT', 3600))
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.environ.get('SESSION_LIFETIME_DAYS', 14)))
    
    # Override these in environment variables for production
    SECRET_KEY = os.environ.get('SECRET_KEY', None)
    if not SECRET_KEY:
        # Warning only, don't prevent app from running
        import warnings
        warnings.warn("No SECRET_KEY set for production environment - using insecure default")
        SECRET_KEY = 'production-needs-better-secret-key'
    
    # SSL settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Use the base DATABASE_URI if not explicitly set for production
    # This allows flexibility during development and containerization
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or Config.SQLALCHEMY_DATABASE_URI
