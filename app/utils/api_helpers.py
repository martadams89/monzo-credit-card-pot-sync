"""Utility functions for API interaction and error handling"""

import time
import logging
import functools
from collections import deque

log = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter for API calls"""
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    def __call__(self):
        """Check if a call is allowed and register it if so"""
        now = time.time()
        # Remove expired timestamps
        while self.calls and now - self.calls[0] > self.period:
            self.calls.popleft()
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def wait_if_needed(self):
        """Wait until rate limit allows a new call"""
        while not self():
            time.sleep(0.1)
        return True

def retry_on_exception(max_retries=3, retry_delay=1.0, backoff_factor=2, allowed_exceptions=(Exception,)):
    """Retry decorator with exponential backoff for API calls"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = retry_delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    retries += 1
                    if retries >= max_retries:
                        log.error(f"Maximum retries ({max_retries}) reached for {func.__name__}")
                        raise
                    
                    log.warning(
                        f"Attempt {retries}/{max_retries} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # This should never be reached due to the raise above
            raise RuntimeError("Unexpected code path in retry decorator")
        return wrapper
    return decorator

def transaction_safe(db_session):
    """Decorator for transaction-safe database operations"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                db_session.commit()
                return result, None
            except Exception as e:
                db_session.rollback()
                log.error(f"Database operation failed: {e}")
                return None, e
        return wrapper
    return decorator

def validate_balance_change(account_type, previous, current, threshold_pct=100, threshold_amount=50000):
    """Validate that a balance change looks reasonable
    
    Args:
        account_type: The account identifier for logging
        previous: Previous balance (in minor currency units, e.g. pennies)
        current: Current balance (in minor currency units)
        threshold_pct: Maximum percentage increase allowed (default 100%)
        threshold_amount: Maximum absolute increase allowed (default £500)
        
    Returns:
        bool: True if the change is reasonable, False otherwise
    """
    if previous is None or previous == 0:
        return True  # First run or zero balance, nothing to compare
    
    increase = current - previous
    if increase < 0:
        return True  # Balance decreased, always valid
        
    # Check for unreasonably large increases
    if (current > previous * (1 + threshold_pct/100)) and (increase > threshold_amount):
        log.warning(
            f"SUSPICIOUS: {account_type} balance increased by more than {threshold_pct}% "
            f"and £{threshold_amount/100:.2f} (from £{previous/100:.2f} to £{current/100:.2f})"
        )
        return False
    
    return True
