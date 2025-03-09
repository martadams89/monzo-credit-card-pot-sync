"""Rate limiting utility for API endpoints."""

import logging
import time
from functools import wraps
from flask import request, jsonify, current_app, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = None

def init_app(app):
    """Initialize rate limiter with Flask app."""
    global limiter
    
    # Configure rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Register route decorator
    app.rate_limit = rate_limit

def rate_limit(limits, key_func=None):
    """Custom decorator for rate limiting specific routes.
    
    Args:
        limits: List of rate limit strings (e.g. "5 per minute")
        key_func: Function to generate rate limit key (defaults to IP address)
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not limiter:
                # If limiter is not initialized, just call the function
                return f(*args, **kwargs)
                
            # Apply rate limiting
            limiter.limit(limits, key_func=key_func)(f)(*args, **kwargs)
            
            # Call the original function
            return f(*args, **kwargs)
            
        return decorated_function
        
    return decorator

def api_rate_limit(limits):
    """Rate limit decorator specifically for API endpoints.
    
    This decorator also handles rate limit exceeded by returning a proper JSON response.
    
    Args:
        limits: List of rate limit strings
        
    Returns:
        Decorated function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not limiter:
                return f(*args, **kwargs)
                
            # Track request time
            start_time = time.time()
            g.start_time = start_time
            
            try:
                # Apply rate limiting
                return limiter.limit(limits)(f)(*args, **kwargs)
            except Exception as e:
                # Check if it's a rate limit exception
                if 'Rate limit exceeded' in str(e):
                    logger.warning(f"Rate limit exceeded for {request.path} from {get_remote_address()}")
                    
                    # Return JSON response for rate limiting
                    response = jsonify({
                        'error': 'rate_limit_exceeded',
                        'message': 'Rate limit exceeded. Please try again later.',
                        'status': 429
                    })
                    response.status_code = 429
                    return response
                    
                # Re-raise other exceptions
                raise
                
        return decorated_function
        
    return decorator
