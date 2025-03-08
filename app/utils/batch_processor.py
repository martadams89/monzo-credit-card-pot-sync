"""Batch processing utilities for database operations"""

import logging
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger(__name__)

class BatchProcessor:
    """Process operations in batches for better performance"""
    
    def __init__(self, db_session, batch_size=100):
        self.db_session = db_session
        self.batch_size = batch_size
        self.current_batch = []
        
    def add(self, item):
        """Add an item to the current batch"""
        self.current_batch.append(item)
        
        if len(self.current_batch) >= self.batch_size:
            self.flush()
            
    def flush(self):
        """Flush the current batch to the database"""
        if not self.current_batch:
            return
            
        try:
            self.db_session.add_all(self.current_batch)
            self.db_session.flush()
            self.current_batch = []
        except SQLAlchemyError as e:
            log.error(f"Error flushing batch: {e}")
            self.db_session.rollback()
            raise
            
    def execute_with_batching(self, items, operation):
        """Execute an operation on items with batching"""
        count = 0
        
        for item in items:
            try:
                result = operation(item)
                self.add(result)
                count += 1
            except Exception as e:
                log.error(f"Error processing item {item}: {e}")
                
        # Flush any remaining items
        self.flush()
        return count
