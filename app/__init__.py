"""Initialize the application."""

import os
import logging
import logging.handlers
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Import config classes
from app.config import Config, DevelopmentConfig, TestingConfig, ProductionConfig

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
csrf = CSRFProtect()

def create_app(test_config=None):
    """Create and configure the Flask application."""
    # Create the Flask app
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure app based on environment
    env = os.environ.get('FLASK_ENV', 'development')
    
    if test_config:
        app.config.from_mapping(test_config)
    elif env == 'production':
        app.config.from_object('app.config.ProductionConfig')
    elif env == 'testing':
        app.config.from_object('app.config.TestingConfig')
    else:
        app.config.from_object('app.config.DevelopmentConfig')
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Set up logging
    configure_logging(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register template filters
    from app.utils.template_helpers import register_template_filters
    register_template_filters(app)
    
    # Import models to ensure they're registered with SQLAlchemy
    with app.app_context():
        from app.models.user import User
        from app.models.account import Account
        from app.models.sync_record import SyncRecord
        from app.models.setting import Setting
        
        # Run database migrations if needed
        # Fix the import path - use relative import
        from .db_migrations import check_and_apply_migrations
        check_and_apply_migrations(app, db)
    
    return app

def configure_logging(app):
    """Configure application logging."""
    log_dir = app.config.get('LOG_DIR', 'logs')
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Set up logging
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(pathname)s:%(lineno)d]'
    )
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'), 
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Set level based on config
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set log level for external libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

def register_blueprints(app):
    """Register Flask blueprints."""
    # Import blueprints
    from app.auth import auth_bp
    from app.main import main_bp
    from app.dashboard import dashboard_bp
    from app.settings import settings_bp
    from app.accounts import accounts_bp
    from app.admin import admin_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(admin_bp)

def register_error_handlers(app):
    """Register error handlers."""
    from app.errors import register_error_handlers as register_app_error_handlers
    register_app_error_handlers(app)