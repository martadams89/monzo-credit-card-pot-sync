import os
import logging
from datetime import datetime
from flask import Flask, render_template

from app.extensions import init_extensions
from app.errors import register_error_handlers
from app.utils.scheduler import init_scheduler, shutdown_scheduler

def create_app(test_config=None):
    """Application factory function."""
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    if test_config is None:
        # Load the config from config.py
        from app.config import get_config
        config_name = os.environ.get('FLASK_ENV', 'default')
        app.config.from_object(get_config(config_name))
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Configure logging
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize extensions
    from app.extensions import init_extensions
    init_extensions(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Add template filters
    @app.template_filter('format_currency')
    def format_currency(value, currency='GBP'):
        try:
            value = float(value) / 100  # Convert from pence to pounds
            if currency == 'GBP':
                return f'£{value:.2f}'
            elif currency == 'EUR':
                return f'€{value:.2f}'
            elif currency == 'USD':
                return f'${value:.2f}'
            else:
                return f'{value:.2f} {currency}'
        except (ValueError, TypeError):
            return '0.00'
    
    # Add context processors
    @app.context_processor
    def utility_processor():
        return {
            'now': datetime.utcnow(),
            'app_name': app.config.get('APP_NAME', 'Monzo Credit Card Pot Sync')
        }
    
    # Initialize scheduler in non-testing environments
    if not app.config.get('TESTING'):
        init_scheduler(app)
    
    # Add teardown handler to clean up resources
    @app.teardown_appcontext
    def teardown_db(exception=None):
        """Clean up at the end of the request."""
        from app.extensions import db
        db.session.remove()
    
    @app.before_request
    def before_request():
        """Process request before handling."""
        pass
    
    return app

def register_blueprints(app):
    """Register all blueprints with the application."""
    # Import blueprints
    from app.web.home import home_bp
    from app.web.auth import auth_bp
    from app.web.monzo import monzo_bp
    from app.web.profile import profile_bp
    from app.web.admin import admin_bp
    from app.web.api import api_bp
    from app.web.webhooks import webhooks_bp
    from app.web.health import health_bp
    from app.web.backup import backup_bp
    
    # Register blueprints
    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(monzo_bp, url_prefix='/monzo')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(backup_bp, url_prefix='/backup')