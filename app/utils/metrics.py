"""Metrics collection for sync process"""

import time
from collections import Counter
import logging

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
