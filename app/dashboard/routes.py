"""Routes for the dashboard."""

import logging
import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.services.container import container
from app.models.account import Account
from app.models.sync_record import SyncRecord
from app.dashboard.forms import SyncForm
from app.extensions import db

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard index page."""
    # Get user's accounts
    credit_card_accounts = Account.query.filter_by(user_id=current_user.id, type='credit_card').all()
    monzo_accounts = Account.query.filter_by(user_id=current_user.id, type='monzo').all()
    
    # Get pot mappings
    pot_service = container().get('pot_service')
    pot_mappings = pot_service.get_pot_mappings(current_user.id)
    
    # Get account data for the view
    account_data = []
    for cc_account in credit_card_accounts:
        # Skip accounts without pot mappings
        if str(cc_account.id) not in pot_mappings:
            continue
            
        # Calculate synchronization percentage
        sync_percentage = 0
        if cc_account.cooldown_ref_card_balance is not None and cc_account.cooldown_ref_pot_balance is not None:
            card_balance_abs = abs(cc_account.cooldown_ref_card_balance)
            if card_balance_abs > 0:
                sync_percentage = min(100, round((cc_account.cooldown_ref_pot_balance / card_balance_abs) * 100))
        
        account_data.append({
            'account': cc_account,
            'card_balance': cc_account.cooldown_ref_card_balance or 0,
            'pot_balance': cc_account.cooldown_ref_pot_balance or 0,
            'sync_percentage': sync_percentage,
            'cooldown_active': cc_account.is_in_cooldown(),
            'cooldown_expires': cc_account.get_cooldown_expiry()
        })
    
    # Get recent sync history
    recent_syncs = SyncRecord.query.filter_by(user_id=current_user.id).order_by(
        SyncRecord.timestamp.desc()
    ).limit(5).all()
    
    # Get sync statistics
    history_repo = container().get('history_repository')
    sync_history = None
    if history_repo:
        sync_history = history_repo.get_sync_stats_for_user(current_user.id, days=30)
    
    # Count sync records
    total_syncs = SyncRecord.query.filter_by(user_id=current_user.id).count()
    successful_syncs = SyncRecord.query.filter_by(user_id=current_user.id, status='success').count()
    failed_syncs = SyncRecord.query.filter_by(user_id=current_user.id, status='error').count()
    
    # Get next sync time
    scheduler_service = container().get('scheduler_service')
    next_sync = None
    if scheduler_service:
        next_sync = scheduler_service.get_next_sync_time(current_user.id)
    
    # Get user's notification settings
    setting_repository = container().get('setting_repository')
    settings_key = f'notification_settings:{current_user.id}'
    settings_json = setting_repository.get(settings_key)
    
    try:
        notification_settings = json.loads(settings_json) if settings_json else {}
    except json.JSONDecodeError:
        notification_settings = {}
    
    notification_settings = {
        'email_enabled': notification_settings.get('email_enabled', False),
        'notify_success': notification_settings.get('notify_success', True),
        'notify_error': notification_settings.get('notify_error', True),
        'notify_auth': notification_settings.get('notify_auth', True)
    }
    
    return render_template('dashboard/index.html',
                          title='Dashboard',
                          account_data=account_data,
                          sync_history=sync_history,
                          recent_syncs=recent_syncs,
                          total_syncs=total_syncs,
                          successful_syncs=successful_syncs,
                          failed_syncs=failed_syncs,
                          next_sync=next_sync,
                          notification_settings=notification_settings)

@dashboard_bp.route('/admin')
@login_required
def admin():
    """Admin dashboard page."""
    # Redirect non-admin users
    if not current_user.is_admin:
        flash('You need to be an administrator to access this page.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Redirect to admin blueprint
    return redirect(url_for('admin.index'))

@dashboard_bp.route('/manual-sync', methods=['GET'])
@login_required
def manual_sync():
    """Manual synchronization page."""
    form = SyncForm()
    return render_template('dashboard/manual_sync.html',
                          title='Manual Sync',
                          form=form)

@dashboard_bp.route('/sync-now', methods=['POST'])
@login_required
def sync_now():
    """Trigger synchronization manually."""
    form = SyncForm()
    
    if form.validate_on_submit():
        # Get sync service
        sync_service = container().get('sync_service')
        
        if not sync_service:
            flash('Sync service not available.', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Run synchronization
        force = bool(form.force.data)
        result = sync_service.sync_user_accounts(current_user.id, force=force)
        
        # Process result
        if result['success']:
            if result['accounts_synced'] > 0:
                flash(f"Successfully synchronized {result['accounts_synced']} accounts.", 'success')
            else:
                flash(f"No accounts needed synchronization. {result['accounts_skipped']} accounts were skipped.", 'info')
        else:
            flash(f"Synchronization had errors: {', '.join(result['errors'])}", 'error')
        
        return redirect(url_for('dashboard.index'))
    
    return render_template('dashboard/manual_sync.html',
                          title='Manual Sync',
                          form=form)

@dashboard_bp.route('/sync/<int:sync_id>/details')
@login_required
def sync_details(sync_id):
    """Get details of a specific sync record."""
    sync_record = SyncRecord.query.filter_by(
        id=sync_id, user_id=current_user.id
    ).first_or_404()
    
    try:
        details = json.loads(sync_record.details) if sync_record.details else {}
        return jsonify(details)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in sync record"})

@dashboard_bp.route('/clear-cooldown/<int:account_id>', methods=['POST'])
@login_required
def clear_cooldown(account_id):
    """Clear cooldown period for an account."""
    account = Account.query.filter_by(
        id=account_id, user_id=current_user.id
    ).first_or_404()
    
    account.cooldown_until = None
    db.session.commit()
    
    flash(f"Cooldown cleared for account {account.display_name()}", 'success')
    return redirect(url_for('dashboard.index'))