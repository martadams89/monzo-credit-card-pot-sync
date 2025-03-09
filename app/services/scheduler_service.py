"""Service for managing synchronization schedules."""

import logging
import json
from datetime import datetime, timedelta
from app.extensions import scheduler

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing scheduled synchronization tasks."""
    
    def __init__(self, setting_repository, sync_service):
        """Initialize the scheduler service.
        
        Args:
            setting_repository: Repository for accessing settings
            sync_service: Service for performing synchronization
        """
        self.setting_repository = setting_repository
        self.sync_service = sync_service
    
    def update_sync_schedule(self, user_id=None):
        """Update synchronization schedule based on settings.
        
        Args:
            user_id: Optional user ID to update schedule for specific user
        """
        try:
            # If user_id is provided, update schedule for that user only
            if user_id:
                self._update_user_schedule(user_id)
                return
                
            # Otherwise, update global schedule
            enabled = self.setting_repository.get('enable_sync', 'true').lower() == 'true'
            interval = self._get_sync_interval()
            
            # Update or create the job
            job_id = 'sync_all_accounts'
            
            if scheduler.get_job(job_id):
                if enabled:
                    scheduler.modify_job(
                        job_id,
                        trigger='interval',
                        minutes=interval
                    )
                    logger.info(f"Updated sync schedule: every {interval} minutes")
                else:
                    scheduler.pause_job(job_id)
                    logger.info("Paused automatic synchronization")
            else:
                if enabled:
                    scheduler.add_job(
                        id=job_id,
                        func=self.sync_service.sync_all_accounts,
                        trigger='interval',
                        minutes=interval,
                        replace_existing=True
                    )
                    logger.info(f"Created sync schedule: every {interval} minutes")
        except Exception as e:
            logger.error(f"Error updating sync schedule: {str(e)}")
    
    def _update_user_schedule(self, user_id):
        """Update synchronization schedule for a specific user.
        
        Args:
            user_id: User ID to update schedule for
        """
        # Get user's sync settings
        settings_key = f'sync_settings:{user_id}'
        settings_json = self.setting_repository.get(settings_key)
        
        try:
            settings = json.loads(settings_json) if settings_json else {}
        except json.JSONDecodeError:
            settings = {}
        
        enabled = settings.get('enable_sync', True)
        interval = settings.get('sync_interval', 2)
        
        # Update or create the job
        job_id = f'sync_user_{user_id}'
        
        if scheduler.get_job(job_id):
            if enabled:
                scheduler.modify_job(
                    job_id,
                    trigger='interval',
                    minutes=interval
                )
                logger.info(f"Updated sync schedule for user {user_id}: every {interval} minutes")
            else:
                scheduler.pause_job(job_id)
                logger.info(f"Paused automatic synchronization for user {user_id}")
        else:
            if enabled:
                scheduler.add_job(
                    id=job_id,
                    func=self._sync_user_accounts,
                    args=[user_id],
                    trigger='interval',
                    minutes=interval,
                    replace_existing=True
                )
                logger.info(f"Created sync schedule for user {user_id}: every {interval} minutes")
    
    def _sync_user_accounts(self, user_id):
        """Wrapper function to sync a user's accounts."""
        return self.sync_service.sync_user_accounts(user_id)
    
    def _get_sync_interval(self):
        """Get the global sync interval from settings."""
        interval_str = self.setting_repository.get('sync_interval', '2')
        try:
            interval = int(interval_str)
            return max(1, interval)  # Ensure minimum interval of 1 minute
        except ValueError:
            logger.warning(f"Invalid sync interval: {interval_str}, using default of 2 minutes")
            return 2
    
    def get_next_sync_time(self, user_id):
        """Get the next scheduled sync time for a user.
        
        Args:
            user_id: User ID to get next sync time for
            
        Returns:
            datetime: Next sync time or None if not scheduled
        """
        job_id = f'sync_user_{user_id}'
        job = scheduler.get_job(job_id)
        
        if not job:
            # Check if user is using global schedule
            settings_key = f'sync_settings:{user_id}'
            settings_json = self.setting_repository.get(settings_key)
            
            try:
                settings = json.loads(settings_json) if settings_json else {}
            except json.JSONDecodeError:
                settings = {}
            
            if settings.get('enable_sync', True):
                job = scheduler.get_job('sync_all_accounts')
        
        if job and job.next_run_time:
            return job.next_run_time
            
        return None
