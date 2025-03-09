"""Base API client with improved error handling and retry logic."""

import logging
import time
from functools import wraps
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

log = logging.getLogger("api_client")

class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message, status_code=None, response=None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)

class AuthenticationError(APIError):
    """Authentication error with API."""
    pass

class RateLimitError(APIError):
    """Rate limit exceeded error."""
    pass

class ServerError(APIError):
    """Server-side API error."""
    pass

def retry(max_tries=3, delay=1, backoff=2, exceptions=(RequestException, Timeout, ConnectionError)):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay
            last_exception = None
            
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    msg = f"{func.__name__}: {str(e)}, Retrying in {mdelay} seconds..."
                    log.warning(msg)
                    
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

class APIClient:
    """Base API client with error handling and retries."""
    
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
    
    @retry()
    def request(self, method, endpoint, headers=None, params=None, data=None, json=None):
        """Make an HTTP request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                timeout=self.timeout
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            return response.json() if response.content else None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed", status_code=e.response.status_code, response=e.response)
            elif e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded", status_code=e.response.status_code, response=e.response)
            elif e.response.status_code >= 500:
                raise ServerError(f"Server error: {e}", status_code=e.response.status_code, response=e.response)
            else:
                raise APIError(f"HTTP error: {e}", status_code=e.response.status_code, response=e.response)
        except (ConnectionError, Timeout) as e:
            raise APIError(f"Connection error: {e}")
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")
