"""Background job queue implementation"""

import threading
import queue
import logging
import time
import traceback
from functools import wraps

log = logging.getLogger(__name__)

class JobQueue:
    """Simple background job queue"""
    
    def __init__(self, num_workers=2):
        self.queue = queue.Queue()
        self.workers = []
        self.running = False
        self.num_workers = num_workers
        
    def start(self):
        """Start the worker threads"""
        if self.running:
            return
            
        self.running = True
        
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"JobQueue-Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            
        log.info(f"Started {self.num_workers} job queue workers")
        
    def stop(self):
        """Stop the worker threads"""
        self.running = False
        
        # Add None jobs to signal workers to exit
        for _ in range(self.num_workers):
            self.queue.put(None)
            
        # Wait for all workers to finish
        for worker in self.workers:
            worker.join(timeout=5.0)
            
        log.info("Job queue stopped")
        
    def enqueue(self, job_func, *args, **kwargs):
        """Add a job to the queue"""
        if not self.running:
            raise RuntimeError("JobQueue is not running")
            
        self.queue.put((job_func, args, kwargs))
        
    def async_task(self, func):
        """Decorator to make a function run asynchronously"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.enqueue(func, *args, **kwargs)
        return wrapper
        
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                # Get a job from the queue
                job = self.queue.get(timeout=1.0)
                
                # None is the signal to exit
                if job is None:
                    break
                    
                func, args, kwargs = job
                
                try:
                    log.debug(f"Executing job {func.__name__}")
                    func(*args, **kwargs)
                except Exception as e:
                    log.error(f"Error executing job {func.__name__}: {e}")
                    log.error(traceback.format_exc())
                finally:
                    # Mark the job as done
                    self.queue.task_done()
                    
            except queue.Empty:
                # Queue timeout, just loop again
                continue

# Initialize the queue
job_queue = JobQueue()

# Example usage in app/__init__.py:
# job_queue.start()
# app.teardown_appcontext(lambda exc: job_queue.stop())
