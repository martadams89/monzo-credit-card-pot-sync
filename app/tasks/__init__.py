"""Background task processing."""

from concurrent.futures import ThreadPoolExecutor
import logging

log = logging.getLogger("tasks")

# Create a thread pool executor
executor = ThreadPoolExecutor(max_workers=4)

def init_tasks(app):
    """Initialize the task system with the Flask app."""
    # Configure any task-related settings here
    worker_count = app.config.get('TASK_WORKERS', 4)
    
    # Update the executor if needed
    global executor
    executor = ThreadPoolExecutor(max_workers=worker_count)
    
    # Register scheduled tasks
    with app.app_context():
        from app.tasks.sync_tasks import setup_sync_jobs
        from app.tasks.backup_tasks import setup_backup_jobs
        from app.tasks.cleanup_tasks import setup_cleanup_jobs
        
        setup_sync_jobs(app)
        setup_backup_jobs(app)
        setup_cleanup_jobs(app)
    
    # Register shutdown to clean up executor
    @app.teardown_appcontext
    def shutdown_executor(exception=None):
        executor.shutdown(wait=False)
