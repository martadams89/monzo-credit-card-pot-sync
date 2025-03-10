import logging
import threading
import time
import schedule
import datetime

from app.services.sync_service import SyncService
from app.models.monzo_repository import MonzoRepository
from app.services.monzo_api import MonzoAPIService
from app.extensions import db
from app.utils.notifications import send_notification
from app.models.monzo import MonzoAccount

log = logging.getLogger(__name__)

class SyncScheduler:
    """Scheduler for running periodic synchronization tasks."""
    
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.monzo_repository = MonzoRepository(db)
        self.monzo_api = MonzoAPIService()
        self.sync_service = SyncService(self.monzo_repository, self.monzo_api)
    
    def start(self):
        """Start the scheduler thread."""
        if self.thread is not None and self.thread.is_alive():
            log.warning("Scheduler is already running")
            return
            
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        log.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler thread."""
        if self.thread is None or not self.thread.is_alive():
            log.warning("Scheduler is not running")
            return
            
        log.info("Stopping scheduler...")
        self.stop_event.set()
        self.thread.join(timeout=5)
        log.info("Scheduler stopped")
    
    def _run(self):
        """Main scheduler loop."""
        # Schedule daily sync jobs
        schedule.every().day.at("01:00").do(self._run_daily_sync)
        
        # Schedule a periodic task to refresh Monzo token cache
        schedule.every(12).hours.do(self._refresh_tokens)
        
        while not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(60)  # Check schedule every minute
    
    def _run_daily_sync(self):
        """Run the daily sync job."""
        log.info("Running daily sync job")
        try:
            result = self.sync_service.execute_daily_rules()
            log.info(f"Daily sync complete: {result['success']} succeeded, {result['error']} failed, {result['skipped']} skipped")
        except Exception as e:
            log.error(f"Error in daily sync job: {str(e)}")
    
    def _refresh_tokens(self):
        """Refresh access tokens to keep them valid."""
        log.info("Refreshing tokens")
        try:
            # Get all active Monzo accounts
            accounts = db.session.query(MonzoAccount).filter_by(is_active=True).all()
            
            current_time = int(time.time())
            
            for account in accounts:
                # Check if token is within expiry window (24 hours)
                if account.token_expires_at - current_time < 86400:  # 24 hours in seconds
                    log.info(f"Refreshing token for account {account.id}")
                    try:
                        tokens = self.monzo_api.refresh_access_token(account)
                        
                        # Update account with new tokens
                        account.access_token = tokens['access_token']
                        account.refresh_token = tokens['refresh_token']
                        account.token_expires_at = current_time + tokens['expires_in']
                        account.last_refreshed = datetime.datetime.utcnow()
                        db.session.commit()
                        
                        log.info(f"Successfully refreshed token for account {account.id}")
                    except Exception as e:
                        log.error(f"Error refreshing token for account {account.id}: {str(e)}")
        except Exception as e:
            log.error(f"Error in token refresh job: {str(e)}")

# Singleton instance
scheduler = SyncScheduler()

def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""
    if app.config.get('TESTING'):
        log.info("Testing mode - scheduler disabled")
        return
        
    with app.app_context():
        log.info("Starting scheduler")
        try:
            scheduler.start()
        except Exception as e:
            log.error(f"Failed to start scheduler: {str(e)}")

def shutdown_scheduler():
    """Shutdown the scheduler."""
    log.info("Shutting down scheduler")
    try:
        scheduler.stop()
    except Exception as e:
        log.error(f"Error shutting down scheduler: {str(e)}")
