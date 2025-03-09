"""Tasks for cleaning up data."""

import logging
from app.extensions import scheduler
from app.services.container import container

log = logging.getLogger("cleanup_tasks")

def cleanup_expired_cooldowns():
    """Clean up expired cooldown periods."""
    cooldown_service = container().get('cooldown_service')
    if cooldown_service:
        count = cooldown_service.cleanup_expired()
        if count > 0:
            log.info(f"Cleaned up {count} expired cooldown periods")

def setup_cleanup_jobs(app):
    """Register cleanup jobs with the scheduler."""
    # Clean up expired cooldowns every hour
    scheduler.add_job(
        id='cleanup_expired_cooldowns',
        func=cleanup_expired_cooldowns,
        trigger='interval',
        hours=1,
        replace_existing=True
    )
    
    app.logger.info("Scheduled cleanup jobs registered")
