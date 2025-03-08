"""Security configurations and middleware"""

from flask import abort, request
import os
import secrets
import time

def init_security(app):
    """Initialize security features for Flask app"""
    # Set secure cookie settings
    app.config['SESSION_COOKIE_SECURE'] = app.config.get('ENV') != 'development'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
    
    # Generate a random secret key if not set
    if not app.secret_key or app.secret_key == 'dev_key':
        app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Add security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        return response
    
    # Basic rate limiting
    if app.config.get('ENABLE_RATE_LIMIT', True) and app.config.get('ENV') != 'development':
        requests_history = {}
        
        @app.before_request
        def limit_requests():
            # Skip rate limiting for static files
            if request.path.startswith('/static/'):
                return None
                
            # Rate limit settings
            RATE_LIMIT = 60  # requests per minute
            WINDOW = 60  # seconds
            
            client_ip = request.remote_addr
            current_time = time.time()
            
            # Clean up old entries
            for ip in list(requests_history.keys()):
                if current_time - requests_history[ip]['timestamp'] > WINDOW:
                    del requests_history[ip]
            
            # Check if client IP exists in history
            if client_ip in requests_history:
                if requests_history[client_ip]['count'] >= RATE_LIMIT:
                    abort(429, "Too many requests. Please try again later.")
                requests_history[client_ip]['count'] += 1
            else:
                requests_history[client_ip] = {
                    'count': 1,
                    'timestamp': current_time
                }
