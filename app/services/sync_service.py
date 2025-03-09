"""Service for synchronizing credit card balances with Monzo pots."""

import json
import logging
import concurrent.futures
from datetime import datetime, timedelta
from app.models.account import Account
from app.models.sync_record import SyncRecord
from app.extensions import db
from app.utils.metrics import SyncMetrics

logger = logging.getLogger(__name__)

class SyncService:
    """Service for synchronizing credit card balances with Monzo pots."""
    
    def __init__(self, monzo_service, truelayer_service, pot_service, setting_repository):
        """Initialize the sync service with required dependencies."""
        self.monzo_service = monzo_service
        self.truelayer_service = truelayer_service
        self.pot_service = pot_service
        self.setting_repository = setting_repository
    
    def sync_all_accounts(self):
        """Synchronize all user accounts in parallel."""
        from app.models.user import User
        
        metrics = SyncMetrics()
        metrics.start_section("sync_all")
        
        # Get active users
        users = User.query.filter_by(is_active=True).all()
        results = {
            'status': 'completed',
            'total_users': len(users),
            'successful_syncs': 0,
            'failed_syncs': 0,
            'accounts_processed': []
        }
        
        # Use ThreadPoolExecutor to run sync in parallel 
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit sync tasks for each user
            future_to_user = {
                executor.submit(self.sync_user_accounts, user.id): user 
                for user in users
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_user):
                user = future_to_user[future]
                try:
                    result = future.result()
                    results['accounts_processed'].append(result)
                    
                    if result['success']:
                        results['successful_syncs'] += 1
                    else:
                        results['failed_syncs'] += 1
                except Exception as e:
                    logger.exception(f"Error syncing accounts for user {user.id}")
                    results['failed_syncs'] += 1
        
        metrics.end_section("sync_all")
        metrics_data = metrics.finalize()
        
        return results
    
    def sync_user_accounts(self, user_id, force=False):
        """Synchronize accounts for a specific user."""
        metrics = SyncMetrics()
        metrics.start_section("sync_user")
        
        # Initialize result
        result = {
            'success': True,
            'accounts_synced': 0,
            'accounts_skipped': 0,
            'errors': [],
            'details': []
        }
        
        try:
            # Get credit card accounts for user
            credit_card_accounts = Account.query.filter_by(user_id=user_id, type='credit_card').all()
            
            # Get monzo accounts for user
            monzo_accounts = Account.query.filter_by(user_id=user_id, type='monzo').all()
            
            # Get pot mappings
            pot_mappings = self.pot_service.get_pot_mappings(user_id)
            
            # Handle no accounts gracefully
            if not credit_card_accounts or not monzo_accounts:
                logger.info(f"No accounts to sync for user {user_id}")
                metrics.end_section("sync_user")
                return result
                
            # Get user's sync settings
            settings_key = f'sync_settings:{user_id}'
            settings_json = self.setting_repository.get(settings_key)
            
            try:
                settings = json.loads(settings_json) if settings_json else {}
            except json.JSONDecodeError:
                settings = {}
                
            threshold_percentage = settings.get('threshold_percentage', 5)
            
            # Process each credit card account
            for cc_account in credit_card_accounts:
                account_metrics = SyncMetrics()
                account_metrics.start_section(f"account_{cc_account.id}")
                
                account_result = {
                    'account_id': cc_account.id,
                    'account_name': cc_account.display_name(),
                    'status': 'skipped',
                    'balance': 0,
                    'pot_balance': 0
                }
                
                try:
                    # Skip if no pot mapping exists
                    pot_id = pot_mappings.get(str(cc_account.id))
                    if not pot_id:
                        logger.info(f"No pot mapping for account {cc_account.id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'no_pot_mapping'
                        result['details'].append(account_result)
                        continue
                    
                    # Skip if in cooldown period (unless forced)
                    if not force and cc_account.is_in_cooldown():
                        logger.info(f"Account {cc_account.id in cooldown until {cc_account.cooldown_until}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'in_cooldown'
                        account_result['cooldown_until'] = cc_account.cooldown_until
                        result['details'].append(account_result)
                        continue
                        
                    # Find matching Monzo account
                    monzo_account = next((a for a in monzo_accounts), None)
                    if not monzo_account:
                        logger.error(f"No Monzo account found for user {user_id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'no_monzo_account'
                        result['details'].append(account_result)
                        continue
                    
                    # Get credit card balance
                    account_metrics.start_section("get_cc_balance")
                    cc_balance = self.truelayer_service.get_total_balance(cc_account)
                    account_metrics.end_section("get_cc_balance")
                    
                    if cc_balance is None:
                        logger.error(f"Could not get credit card balance for account {cc_account.id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'error_cc_balance'
                        result['details'].append(account_result)
                        continue
                        
                    # Get pot balance
                    account_metrics.start_section("get_pot_balance")
                    pot_balance = self.monzo_service.get_pot_balance(monzo_account, pot_id)
                    account_metrics.end_section("get_pot_balance")
                    
                    if pot_balance is None:
                        logger.error(f"Could not get pot balance for account {cc_account.id}, pot {pot_id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'error_pot_balance'
                        result['details'].append(account_result)
                        continue
                    
                    # Update account result with balances
                    account_result['balance'] = cc_balance
                    account_result['pot_balance'] = pot_balance
                    
                    # Calculate absolute credit card balance (credit cards have negative balances)
                    cc_balance_abs = abs(cc_balance)
                    
                    # Calculate difference
                    balance_diff = abs(pot_balance - cc_balance_abs)
                    
                    # Calculate difference percentage
                    diff_percentage = 0
                    if cc_balance_abs > 0:
                        diff_percentage = (balance_diff / cc_balance_abs) * 100
                    
                    # Skip if difference is below threshold
                    if diff_percentage < threshold_percentage and pot_balance > 0:
                        logger.info(f"Difference {diff_percentage:.2f}% below threshold {threshold_percentage}% for account {cc_account.id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'below_threshold'
                        account_result['diff_percentage'] = diff_percentage
                        result['details'].append(account_result)
                        continue
                    
                    # Calculate amount to add or withdraw
                    transfer_amount = cc_balance_abs - pot_balance
                    
                    # Update pot balance
                    account_metrics.start_section("update_pot")
                    if transfer_amount > 0:
                        # Need to add money to pot
                        success = self.monzo_service.deposit_to_pot(monzo_account, pot_id, transfer_amount)
                    else:
                        # Need to withdraw money from pot
                        success = self.monzo_service.withdraw_from_pot(monzo_account, pot_id, abs(transfer_amount))
                    account_metrics.end_section("update_pot")
                    
                    if not success:
                        logger.error(f"Failed to update pot balance for account {cc_account.id}")
                        result['accounts_skipped'] += 1
                        account_result['status'] = 'transfer_failed'
                        account_result['transfer_amount'] = transfer_amount
                        result['details'].append(account_result)
                        continue
                    
                    # Update account cooldown
                    if not force:
                        cc_account.set_cooldown(settings.get('cooldown_hours', 3) if settings.get('enable_cooldown', True) else 0)
                        cc_account.cooldown_ref_card_balance = cc_balance
                        cc_account.cooldown_ref_pot_balance = cc_balance_abs  # After transfer, pot balance should match CC balance
                        cc_account.stable_pot_balance = cc_balance_abs
                        db.session.commit()
                    
                    # Success!
                    result['accounts_synced'] += 1
                    account_result['status'] = 'success'
                    account_result['transfer_amount'] = transfer_amount
                    result['details'].append(account_result)
                    logger.info(f"Successfully synced account {cc_account.id}, transferred {transfer_amount}")
                
                except Exception as e:
                    logger.error(f"Error syncing account {cc_account.id}: {str(e)}")
                    result['errors'].append(f"Account {cc_account.id}: {str(e)}")
                    account_result['status'] = 'error'
                    account_result['error'] = str(e)
                    result['details'].append(account_result)
                
                finally:
                    account_metrics.end_section(f"account_{cc_account.id}")
            
            # Save sync history
            history_repository = self.get_history_repository()
            if history_repository:
                try:
                    history_repository.save_sync_history({
                        'timestamp': datetime.utcnow().isoformat(),
                        'status': 'success' if result['success'] else 'error',
                        'accounts_synced': result['accounts_synced'],
                        'accounts_skipped': result['accounts_skipped'],
                        'errors': result['errors'],
                        'details': result['details']
                    }, user_id)
                except Exception as e:
                    logger.error(f"Error saving sync history: {str(e)}")
            
            # Get user's notification settings
            settings_key = f'notification_settings:{user_id}'
            settings_json = self.setting_repository.get(settings_key)
            
            try:
                notification_settings = json.loads(settings_json) if settings_json else {}
            except json.JSONDecodeError:
                notification_settings = {}
                
            email_enabled = notification_settings.get('email_enabled', False)
            
            # Send email notification if enabled
            if email_enabled:
                self.send_notification_email(user_id, result, notification_settings)
            
        except Exception as e:
            logger.error(f"Error syncing user accounts: {str(e)}")
            result['success'] = False
            result['errors'].append(str(e))
        
        finally:
            metrics.end_section("sync_user")
            
        return result
    
    def get_history_repository(self):
        """Get the history repository from the service container."""
        try:
            from app.services.container import container
            return container().get('history_repository')
        except Exception as e:
            logger.error(f"Error getting history repository: {str(e)}")
            return None
            
    def send_notification_email(self, user_id, result, notification_settings):
        """Send notification email based on sync result and settings."""
        try:
            from app.models.user import User
            user = User.query.get(user_id)
            
            if not user or not user.email:
                return
                
            should_notify = (
                (result['success'] and notification_settings.get('notify_success', True)) or 
                (not result['success'] and notification_settings.get('notify_error', True)) or
                (result.get('auth_error', False) and notification_settings.get('notify_auth', True))
            )
            
            if should_notify:
                from app.services.container import container
                email_service = container().get('email_service')
                
                if email_service:
                    email_service.send_sync_report(user.email, {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'success' if result['success'] else 'error',
                        'accounts_synced': result.get('accounts_synced', 0),
                        'accounts_skipped': result.get('accounts_skipped', 0),
                        'errors': result.get('errors', []),
                        'details': result.get('details', [])
                    })
        except Exception as e:
            logger.error(f"Error sending notification email: {str(e)}")
    
    def get_next_sync_time(self, user_id):
        """Get the estimated next sync time for a user."""
        # Get scheduler service from container
        from app.services.container import container
        scheduler_service = container().get('scheduler_service')
        
        if scheduler_service:
            return scheduler_service.get_next_sync_time(user_id)
            
        return None