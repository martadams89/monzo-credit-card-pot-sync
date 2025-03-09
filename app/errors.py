from flask_sqlalchemy import SQLAlchemy
from flask import render_template
import logging

db = SQLAlchemy()

logger = logging.getLogger(__name__)

class AuthException(Exception):
    """Exception raised for authentication errors."""
    def __init__(self, message, details=None):
        self.message = message
        self.details = details
        super().__init__(message)

def register_error_handlers(app):
    """Register error handlers with the Flask app."""
    
    @app.errorhandler(403)
    def forbidden_page(error):
        """Handle 403 errors."""
        logger.warning(f"403 error: {error}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found_page(error):
        """Handle 404 errors."""
        logger.info(f"404 error: {error}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error_page(error):
        """Handle 500 errors."""
        logger.error(f"500 error: {error}", exc_info=True)
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        """Handle unhandled exceptions."""
        logger.exception("Unhandled exception: %s", str(error))
        return render_template('errors/500.html'), 500