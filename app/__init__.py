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
    init_extensions(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register all blueprints at once using the helper function
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
    
    return app

# Note: Removed duplicate register_error_handlers function since it's already imported

# Add better exception handling for blueprint registration

def register_blueprints(app):
    """Register all blueprints with the application."""
    # Import blueprints
    from app.web.home import home_bp
    from app.web.auth import auth_bp
    
    # Register core blueprints
    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Dynamically register additional blueprints
    blueprint_configs = [
        ('app.web.monzo', 'monzo_bp', '/monzo'),
        ('app.web.profile', 'profile_bp', '/profile'),
        ('app.web.admin', 'admin_bp', '/admin'),
        ('app.web.api', 'api_bp', '/api'),
        ('app.web.webhooks', 'webhooks_bp', '/webhooks'),
        ('app.web.health', 'health_bp', '/health'),
        ('app.web.backup', 'backup_bp', '/backup'),
        ('app.web.pots', 'pots_bp', '/pots'),
        ('app.web.settings', 'settings_bp', '/settings'),
        ('app.web.accounts', 'accounts_bp', '/accounts'),
        ('app.web.errors', 'errors_bp', None),
        ('app.api.v1', 'api_v1_bp', '/api/v1')
    ]
    
    for module_name, blueprint_name, url_prefix in blueprint_configs:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            if url_prefix:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
            else:
                app.register_blueprint(blueprint)
            app.logger.info(f"Registered blueprint: {blueprint_name}")
        except (ImportError, AttributeError) as e:
            app.logger.debug(f"Optional blueprint {blueprint_name} not available: {str(e)}")