"""Scheduled tasks for account synchronization."""

import logging
from datetime import datetime
from app.extensions import scheduler
from app.services.container import container
from app.utils.json_utils import dumps
from app.models.user import User

log = logging.getLogger(__name__)

# Try importing Celery, but make it optional
try:
    from celery import shared_task
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False
    # Create a dummy decorator for compatibility
    def shared_task(*args, **kwargs):
        def wrapper(func):
            return func
        return wrapper if args and callable(args[0]) else wrapper

def run_sync_for_account(account_id):
    """Run synchronization for a single account in the background."""
    log.info(f"Starting background sync for account {account_id}")
    
    try:
        # Get required services
        sync_service = container().get('sync_service')
        account_service = container().get('account_service')
        history_repository = container().get('history_repository')
        metrics_service = container().get('metrics_service')
        
        # Get account
        account = account_service.get_account(account_id)
        if not account:
            log.error(f"Account {account_id} not found")
            return False
            
        # Run sync
        result = sync_service.sync_account(account)
        
        # Save history
        history_data = {
            'status': 'completed' if result['status'] == 'success' else 'error',
            'timestamp': datetime.now().isoformat(),
            'accounts_processed': [result]
        }
        
        if 'error' in result:
            history_data['errors'] = [{'account': account.type, 'error': result['error']}]
            
        history_repository.save_sync_history(dumps(history_data))
        
        # Update metrics
        metrics_service.record_sync(result)
        
        log.info(f"Background sync completed for account {account_id}")
        return True
        
    except Exception as e:
        log.error(f"Error in background sync for account {account_id}: {str(e)}", exc_info=True)
        
        # Save error in history
        try:
            history_data = {
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'accounts_processed': [],
                'errors': [{'account': account_id, 'error': str(e)}]
            }
            
            history_repository = container().get('history_repository')
            history_repository.save_sync_history(dumps(history_data))
        except Exception:
            log.exception("Failed to save error history")
        
        return False

def queue_sync_for_account(account_id):
    """Queue a sync task for a specific account."""
    return executor.submit(run_sync_for_account, account_id)

def run_scheduled_sync():
    """Execute scheduled synchronization of all accounts."""
    sync_service = container().get('sync_service')
    setting_repository = container().get('setting_repository')
    
    # Check if sync is enabled
    sync_enabled = setting_repository.get('enable_sync', 'True').lower() == 'true'
    if not sync_enabled:
        log.info("Scheduled sync is disabled")
        return
        
    log.info("Running scheduled account synchronization")
    
    # Execute sync for all accounts
    result = sync_service.sync_all_accounts()
    
    # Log summary
    if result['status'] == 'completed':
        log.info("Scheduled sync completed successfully")
    elif result['status'] == 'partial':
        log.warning("Scheduled sync partially successful")
    else:
        log.error(f"Scheduled sync failed: {result.get('message', 'Unknown error')}")
    
    # Log detailed stats
    processed = result.get('accounts_processed', [])
    success_count = len([a for a in processed if a.get('status') == 'success'])
    skip_count = len([a for a in processed if a.get('status') == 'skipped'])
    error_count = len([a for a in processed if a.get('status') == 'error'])
    
    log.info(f"Sync stats: {success_count} succeeded, {skip_count} skipped, {error_count} failed")

def setup_sync_jobs(app):
    """Register synchronization jobs with the scheduler."""
    try:
        setting_repository = container().get('setting_repository')
        
        # Get sync schedule from settings
        sync_schedule = setting_repository.get('sync_schedule', '*/30 * * * *')  # Default: Every 30 minutes
        
        # Register the sync job
        scheduler.add_job(
            id='scheduled_sync',
            func=run_scheduled_sync,
            trigger='cron',
            **parse_cron_expression(sync_schedule),
            replace_existing=True
        )
        
        app.logger.info(f"Scheduled sync job registered with cron: {sync_schedule}")
    except Exception as e:
        app.logger.error(f"Failed to setup sync jobs: {str(e)}")

def parse_cron_expression(expression):
    """Parse cron expression into kwargs for APScheduler."""
    parts = expression.split()
    if len(parts) != 5:
        # Invalid cron expression, use default (every 30 minutes)
        return {'minute': '*/30'}
    
    minute, hour, day, month, day_of_week = parts
    return {
        'minute': minute,
        'hour': hour, 
        'day': day,
        'month': month,
        'day_of_week': day_of_week
    }

# Only define this if Celery is available
if HAS_CELERY:
    @shared_task(name="sync_all_accounts", bind=True, max_retries=3)
    def sync_all_accounts_task(self):
        """Synchronize all accounts for all users."""
        sync_service = container().get('sync_service')
        if not sync_service:
            logger.error("Sync service not available")
            return False
            
        users = User.query.filter_by(is_active=True).all()
        results = {
            'total_users': len(users),
            'successful_syncs': 0,
            'failed_syncs': 0
        }
        
        for user in users:
            try:
                result = sync_service.sync_user_accounts(user.id)
                if result['success'] and result['accounts_synced'] > 0:
                    results['successful_syncs'] += 1
                else:
                    results['failed_syncs'] += 1
            except Exception as e:
                logger.error(f"Error syncing accounts for user {user.id}: {str(e)}")
                results['failed_syncs'] += 1
                
        return results
