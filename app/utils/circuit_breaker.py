"""Circuit breaker implementation for API calls"""

import time
import logging
import functools

log = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker for API calls"""
    
    # State constants
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Circuit is broken
    HALF_OPEN = "HALF_OPEN"  # Testing if service is back
    
    def __init__(self, name, failure_threshold=5, recovery_timeout=30, 
                 recovery_threshold=2, excluded_exceptions=None):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.recovery_threshold = recovery_threshold
        self.excluded_exceptions = excluded_exceptions or []
        
        # State
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == self.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    log.info(f"Circuit {self.name}: Switching from OPEN to HALF_OPEN")
                    self.state = self.HALF_OPEN
                    self.success_count = 0
                else:
                    log.warning(f"Circuit {self.name}: Open, rejecting call to {func.__name__}")
                    raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
            
            try:
                result = func(*args, **kwargs)
                
                # On success
                if self.state == self.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.recovery_threshold:
                        log.info(f"Circuit {self.name}: Recovery threshold reached, closing circuit")
                        self.state = self.CLOSED
                        self.failure_count = 0
                
                # Reset failure count on successful closed state call
                elif self.state == self.CLOSED:
                    self.failure_count = 0
                    
                return result
                
            except Exception as e:
                # Don't count excluded exceptions toward failure threshold
                if any(isinstance(e, exc) for exc in self.excluded_exceptions):
                    raise
                
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
                    log.warning(f"Circuit {self.name}: Failure threshold reached, opening circuit")
                    self.state = self.OPEN
                    
                elif self.state == self.HALF_OPEN:
                    log.warning(f"Circuit {self.name}: Failed in HALF_OPEN state, back to OPEN")
                    self.state = self.OPEN
                    
                raise
                
        return wrapper

# Example usage
monzo_balance_circuit = CircuitBreaker("monzo_balance", failure_threshold=3, recovery_timeout=60)
