from flask_sqlalchemy import SQLAlchemy
from flask import render_template
from werkzeug.exceptions import HTTPException

db = SQLAlchemy()

class AppError(Exception):
    """Base exception class for application-specific errors."""
    
    def __init__(self, message=None, details=None, status_code=None):
        super().__init__(message)
        self.message = message or "An unexpected error occurred"
        self.details = details
        self.status_code = status_code or 500

class AuthException(AppError):
    """Exception for authentication errors."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "Authentication error",
            details=details,
            status_code=401
        )

class MonzoAPIError(AppError):
    """Exception for Monzo API errors."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "Monzo API error",
            details=details,
            status_code=500
        )

class TrueLayerAPIError(AppError):
    """Exception for TrueLayer API errors."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "TrueLayer API error",
            details=details,
            status_code=500
        )

class ValidationError(AppError):
    """Exception for data validation errors."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "Validation error",
            details=details,
            status_code=400
        )

class ResourceNotFoundError(AppError):
    """Exception for requests to non-existent resources."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "Resource not found",
            details=details,
            status_code=404
        )

class ForbiddenError(AppError):
    """Exception for unauthorized access to resources."""
    
    def __init__(self, message=None, details=None):
        super().__init__(
            message=message or "Access forbidden",
            details=details,
            status_code=403
        )

def register_error_handlers(app):
    """Register application error handlers."""
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle Werkzeug HTTP exceptions."""
        return render_template(
            f"errors/{e.code}.html", 
            error=e
        ), e.code
    
    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors."""
        return render_template("errors/404.html"), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 errors."""
        return render_template("errors/500.html"), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        """Handle 403 errors."""
        return render_template("errors/403.html"), 403
    
    @app.errorhandler(AppError)
    def handle_app_error(e):
        """Handle application specific errors."""
        if e.status_code == 404:
            return render_template("errors/404.html", error=e), 404
        elif e.status_code == 403:
            return render_template("errors/403.html", error=e), 403
        else:
            return render_template("errors/500.html", error=e), e.status_code or 500