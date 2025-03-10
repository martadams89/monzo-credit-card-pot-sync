from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def role_required(role):
    """Decorator to restrict access to users with a specific role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if current_user.role != role:
                abort(403)  # Forbidden
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to restrict access to admin users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        if not current_user.role == 'admin':
            flash('Access denied. Administrator privileges required.', 'error')
            abort(403)  # Forbidden
            
        return f(*args, **kwargs)
    return decorated_function
