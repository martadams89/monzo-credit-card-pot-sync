"""Security utilities for the application."""

import secrets
import hashlib
from flask import current_app
from datetime import datetime, timedelta

def generate_secure_token(length=32):
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)

def hash_data(data, salt=None):
    """
    Hash data for secure storage.
    
    Args:
        data: The data to hash
        salt: Optional salt
        
    Returns:
        Tuple of (hash, salt)
    """
    if not salt:
        salt = secrets.token_hex(16)
    
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        data.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    )
    
    return key.hex(), salt

def is_rate_limited(key, limit=5, period=60):
    """
    Check if a key is rate limited.
    
    Args:
        key: Unique identifier for rate limiting
        limit: Number of attempts allowed
        period: Time period in seconds
        
    Returns:
        Boolean indicating if rate limited
    """
    from app.extensions import redis
    
    # If Redis not available, fail open but log
    if not redis:
        current_app.logger.warning("Redis not available for rate limiting")
        return False
    
    current_time = datetime.utcnow()
    key_name = f"rate_limit:{key}"
    
    # Add timestamp to list
    redis.lpush(key_name, current_time.timestamp())
    
    # Set expiration if not already set
    redis.expire(key_name, period)
    
    # Remove timestamps outside window
    cutoff = (current_time - timedelta(seconds=period)).timestamp()
    redis.lrem(key_name, 0, cutoff)
    
    # Check count
    count = redis.llen(key_name)
    return count > limit
