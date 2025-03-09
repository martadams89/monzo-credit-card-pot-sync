"""
Flask extension instances.

This module initializes all Flask extensions used throughout the application.
Extensions are initialized without app context to allow for better separation
of concerns and easier testing.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
csrf = CSRFProtect()
mail = Mail()
scheduler = APScheduler()
limiter = Limiter(key_func=get_remote_address)

# Configure login manager
login.login_view = 'auth.login'
login.login_message = 'Please log in to access this page.'
login.login_message_category = 'info'
login.refresh_view = 'auth.login'
login.needs_refresh_message = 'Please log in again to confirm your identity.'
login.needs_refresh_message_category = 'info'

@login.user_loader
def load_user(user_id):
    """Load a user from the database by ID.
    
    This function is required by Flask-Login to load a user from the database
    given their ID (usually from the session cookie).
    
    Args:
        user_id: The ID of the user to load
        
    Returns:
        User object or None if not found
    """
    from app.models.user import User
    return User.query.get(int(user_id))

def init_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Setup scheduler
    scheduler.init_app(app)
    scheduler.start()
    
    # Setup login manager
    login.init_app(app)
    
    # Setup database hooks (e.g. for backups before migrations)
    from app.services.container import container
    
    @migrate.configure
    def configure_alembic(config):
        # Access backup service via container if needed
        backup_service = container().get('backup_service')
        if backup_service:
            # Create backup before migrations (could be implemented as needed)
            pass
        return config
