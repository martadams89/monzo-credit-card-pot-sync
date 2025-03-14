"""
Initialize Flask extensions for the application.

These extensions are instantiated here and initialized in the application factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_apscheduler import APScheduler
from flask_swagger_ui import get_swaggerui_blueprint

# SQLAlchemy for database ORM
db = SQLAlchemy()

# Flask-Migrate for database migrations
migrate = Migrate()

# Flask-Login for user authentication
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Flask-Mail for sending emails
mail = Mail()

# CSRF protection
csrf = CSRFProtect()

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Cache
cache = Cache()

# Scheduler
scheduler = APScheduler()

def init_extensions(app):
    """Initialize all Flask extensions."""
    # Configure SQLAlchemy
    db.init_app(app)
    
    # Add event listener to verify database connections
    @app.before_request
    def ensure_db_connection():
        try:
            # Test database connection
            db.engine.execute('SELECT 1')
        except Exception as e:
            app.logger.error(f"Database connection error: {e}")
            db.session.rollback()
            
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Configure simple caching
    cache_config = {
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
    
    cache.init_app(app, config=cache_config)

    # Initialize scheduler
    scheduler.init_app(app)
    
    # Setup Swagger UI
    swagger_url = '/api/docs'
    api_url = '/static/swagger.json'
    swaggerui_blueprint = get_swaggerui_blueprint(
        swagger_url,
        api_url,
        config={
            'app_name': "Monzo Credit Card Pot Sync API"
        }
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=swagger_url)
    
    # Load user for Flask-Login
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
