"""Task executor for background processing."""

import concurrent.futures
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# Create a thread pool executor for background tasks
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def async_task(f):
    """Decorator to run a function asynchronously."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return executor.submit(f, *args, **kwargs)
    return wrapper

def shutdown():
    """Shutdown the executor gracefully."""
    logger.info("Shutting down task executor")
    executor.shutdown(wait=True)
