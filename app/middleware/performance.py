import time
import logging
from flask import request, g

logger = logging.getLogger(__name__)

class PerformanceMiddleware:
    """Middleware for tracking request performance."""
    
    def __init__(self, app):
        """Initialize the middleware with the app."""
        self.app = app
    
    def __call__(self, environ, start_response):
        """Process the request and track performance."""
        # Start timing the request
        request_start = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            """Custom response handler to track timing."""
            # Record request completion
            duration = time.time() - request_start
            
            # Log performance metrics
            path = environ.get('PATH_INFO', '')
            method = environ.get('REQUEST_METHOD', '')
            status_code = int(status.split(' ')[0])
            
            # Only log if request takes more than 500ms
            if duration > 0.5:
                logger.info(f"SLOW REQUEST: {method} {path} {status_code} - {duration:.4f}s")
            elif status_code >= 400:
                # Always log errors
                logger.info(f"ERROR REQUEST: {method} {path} {status_code} - {duration:.4f}s")
            
            # Call the original start_response
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)
