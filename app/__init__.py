"""Main application package."""

import os
import logging
from flask import Flask
from flask_login import LoginManager
from app.extensions import db, migrate
from app.services.container import setup_services
from app.security import init_security
from app.db_migrations import run_migrations

def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Set default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_key'),
        DATABASE_URL=os.environ.get('DATABASE_URL', 'sqlite:///instance/app.db'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///instance/app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        VERSION='1.0.0',
        SERVER_NAME=os.environ.get('POT_SYNC_LOCAL_URL', '').replace('http://', '').replace('https://', '') or None
    )
    
    # Override config with test config if provided
    if test_config:
        app.config.update(test_config)
    
    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Setup security features
    init_security(app)
    
    # Register blueprints
    from app.auth import auth_bp
    from app.main import main_bp
    from app.dashboard import dashboard_bp
    from app.settings import settings_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp, url_prefix='/main')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Setup login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Setup services
    setup_services(app)
    
    # Setup root route
    @app.route('/')
    def index():
        return {'message': 'Monzo Credit Card Pot Sync API'}
    
    # Run database migrations on startup
    with app.app_context():
        db.create_all()
        run_migrations(db)
    
    return app