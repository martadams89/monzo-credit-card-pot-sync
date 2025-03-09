"""Application metrics and monitoring."""

import time
import logging
import threading
from functools import wraps
from flask import g, request, current_app

logger = logging.getLogger(__name__)

# Dictionary to store metrics
_metrics = {
    'requests': 0,
    'errors': 0,
    'response_times': [],
    'sync_operations': 0,
    'successful_syncs': 0,
    'failed_syncs': 0
}

_metrics_lock = threading.Lock()

def increment(metric, value=1):
    """Increment a metric counter."""
    with _metrics_lock:
        if metric in _metrics:
            _metrics[metric] += value

def record_response_time(duration):
    """Record an API response time."""
    with _metrics_lock:
        _metrics['response_times'].append(duration)
        # Keep only the last 1000 response times
        if len(_metrics['response_times']) > 1000:
            _metrics['response_times'] = _metrics['response_times'][-1000:]

def get_metrics():
    """Get a copy of the current metrics."""
    with _metrics_lock:
        result = dict(_metrics)
        if result['response_times']:
            result['avg_response_time'] = sum(result['response_times']) / len(result['response_times'])
        else:
            result['avg_response_time'] = 0
        return result

def performance_middleware():
    """WSGI middleware to track request performance."""
    def middleware(environ, start_response):
        request_start = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            # Record request completion
            duration = time.time() - request_start
            record_response_time(duration * 1000)  # Store in milliseconds
            
            # Track request counts
            increment('requests')
            
            # Track errors
            status_code = int(status.split(' ')[0])
            if status_code >= 500:
                increment('errors')
                
            return start_response(status, headers, exc_info)
        
        return app(environ, custom_start_response)
    
    return middleware

"""Metrics collection for sync process"""

from collections import Counter

log = logging.getLogger(__name__)

class SyncMetrics:
    """Collect and report metrics for the sync process"""
    
    def __init__(self):
        self.start_time = time.time()
        self.data = {
            "accounts_processed": 0,
            "deposits_made": 0,
            "withdrawals_made": 0,
            "total_deposited": 0,
            "total_withdrawn": 0,
            "cooldowns_active": 0,
            "cooldowns_expired": 0,
            "errors": Counter(),
            "timing": {},
            "section_times": {}
        }
    
    def start_section(self, section_name):
        """Start timing a section"""
        self.data["section_times"][section_name] = {"start": time.time()}
        
    def end_section(self, section_name):
        """End timing a section"""
        if section_name in self.data["section_times"]:
            start_time = self.data["section_times"][section_name].get("start")
            if start_time:
                self.data["section_times"][section_name]["duration"] = time.time() - start_time
                self.data["timing"][section_name] = self.data["section_times"][section_name]["duration"]
    
    def record_deposit(self, amount):
        """Record a deposit to a pot"""
        self.data["deposits_made"] += 1
        self.data["total_deposited"] += amount
    
    def record_withdrawal(self, amount):
        """Record a withdrawal from a pot"""
        self.data["withdrawals_made"] += 1
        self.data["total_withdrawn"] += amount
    
    def record_cooldown_active(self):
        """Record an active cooldown"""
        self.data["cooldowns_active"] += 1
    
    def record_cooldown_expired(self):
        """Record an expired cooldown"""
        self.data["cooldowns_expired"] += 1
    
    def record_account_processed(self):
        """Record that an account was processed"""
        self.data["accounts_processed"] += 1
    
    def record_error(self, error_type, error):
        """Record an error"""
        self.data["errors"][error_type] += 1
        log.error(f"{error_type} error: {error}")
    
    def get_total_duration(self):
        """Get the total duration of the sync process"""
        return time.time() - self.start_time
    
    def finalize(self):
        """Finalize metrics collection"""
        self.data["total_duration"] = self.get_total_duration()
        log.info(f"Sync completed in {self.data['total_duration']:.2f}s")
        log.info(f"Metrics summary: accounts={self.data['accounts_processed']}, "
                 f"deposits={self.data['deposits_made']} (£{self.data['total_deposited']/100:.2f}), "
                 f"withdrawals={self.data['withdrawals_made']} (£{self.data['total_withdrawn']/100:.2f}), "
                 f"cooldowns_active={self.data['cooldowns_active']}, "
                 f"cooldowns_expired={self.data['cooldowns_expired']}")
        
        if self.data["errors"]:
            log.warning(f"Errors during sync: {dict(self.data['errors'])}")
            
        # Convert Counter to dict for JSON serialization
        self.data["errors"] = dict(self.data["errors"])
        return self.data
