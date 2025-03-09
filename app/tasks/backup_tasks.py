"""Scheduled backup tasks."""

import logging
from app.extensions import scheduler
from app.services.container import container

log = logging.getLogger("backup_tasks")

def run_scheduled_backup():
    """Execute scheduled database backup."""
    backup_service = container().get('backup_service')
    setting_repository = container().get('setting_repository')
    
    # Check if backups are enabled
    backup_enabled = setting_repository.get('enable_backups', 'True').lower() == 'true'
    if not backup_enabled:
        log.info("Scheduled backups are disabled")
        return
        
    log.info("Starting scheduled database backup")
    result = backup_service.create_backup(reason="scheduled")
    
    if result['success']:
        log.info(f"Scheduled backup created: {result['file']}")
    else:
        log.error(f"Scheduled backup failed: {result.get('error', 'unknown error')}")

def setup_backup_jobs(app):
    """Register backup jobs with the scheduler."""
    setting_repository = container().get('setting_repository')
    
    # Get backup schedule from settings
    backup_schedule = setting_repository.get('backup_schedule', '0 0 * * *')  # Default: daily at midnight
    
    # Register the backup job
    scheduler.add_job(
        id='scheduled_backup',
        func=run_scheduled_backup,
        trigger='cron',
        **parse_cron_expression(backup_schedule),
        replace_existing=True
    )
    
    app.logger.info(f"Scheduled backup job registered with cron: {backup_schedule}")

def parse_cron_expression(expression):
    """Parse cron expression into kwargs for APScheduler."""
    parts = expression.split()
    if len(parts) != 5:
        # Invalid cron expression, use default (daily at midnight)
        return {'hour': 0, 'minute': 0}
    
    minute, hour, day, month, day_of_week = parts
    return {
        'minute': minute,
        'hour': hour, 
        'day': day,
        'month': month,
        'day_of_week': day_of_week
    }
