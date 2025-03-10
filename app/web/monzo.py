import logging
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from app.models.monzo import MonzoAccount, MonzoPot, SyncRule, SyncHistory
from app.models.monzo_repository import MonzoRepository
from app.services.monzo_api import MonzoAPI, MonzoAPIError
from app.services.sync_service import SyncService
from app.extensions import db

monzo_bp = Blueprint('monzo', __name__)
log = logging.getLogger(__name__)
monzo_repo = MonzoRepository()

@monzo_bp.before_request
@login_required
def before_request():
    """Ensure all monzo routes are protected."""
    pass

@monzo_bp.route('/')
def index():
    """Monzo dashboard showing accounts and pots."""
    accounts = monzo_repo.get_accounts_by_user_id(current_user.id)
    
    # For each account, get the pots and sync rules
    accounts_data = []
    for account in accounts:
        pots = monzo_repo.get_pots_by_account_id(account.id)
        
        # Get sync rules for this account
        rules = db.session.query(SyncRule).filter_by(
            source_account_id=account.id,
            user_id=current_user.id
        ).all()
        
        accounts_data.append({
            'account': account,
            'pots': pots,
            'rules': rules
        })
    
    # Get recent sync history
    history = db.session.query(SyncHistory).filter_by(
        user_id=current_user.id
    ).order_by(SyncHistory.created_at.desc()).limit(10).all()
    
    return render_template(
        'monzo/index.html',
        accounts_data=accounts_data,
        history=history
    )

@monzo_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    """Add a new Monzo account."""
    if request.method == 'POST':
        access_token = request.form.get('access_token')
        
        if not access_token:
            flash('Access token is required', 'error')
            return render_template('monzo/add_account.html')
            
        try:
            # Validate token by making an API call
            api = MonzoAPI(access_token)
            accounts = api.get_accounts()
            
            if not accounts:
                flash('No accounts found with provided access token', 'error')
                return render_template('monzo/add_account.html')
                
            # Check if any account already exists for the user
            for account_data in accounts:
                existing = monzo_repo.get_account_by_id(account_data['id'])
                if existing and existing.user_id == current_user.id:
                    flash(f'Account {account_data["description"]} is already linked', 'warning')
                    continue
                    
                # Create new account record
                account = MonzoAccount(
                    id=account_data['id'],
                    user_id=current_user.id,
                    name=account_data.get('description', 'Monzo Account'),
                    type=account_data.get('type', 'unknown'),
                    access_token=access_token,
                    is_active=True,
                    sync_enabled=True,
                    created_at=datetime.utcnow()
                )
                
                monzo_repo.save_account(account)
                flash(f'Account {account.name} added successfully', 'success')
                
                # Initial data sync
                try:
                    monzo_repo.refresh_account_data(account)
                except Exception as e:
                    log.error(f"Error syncing initial data: {str(e)}")
                
            return redirect(url_for('monzo.index'))
                
        except MonzoAPIError as e:
            flash(f'Invalid access token: {str(e)}', 'error')
            return render_template('monzo/add_account.html')
            
    return render_template('monzo/add_account.html')

@monzo_bp.route('/accounts/<account_id>/refresh', methods=['POST'])
@login_required
def refresh_account(account_id):
    """Refresh account data from Monzo API."""
    account = monzo_repo.get_account_by_id(account_id)
    
    if not account or account.user_id != current_user.id:
        flash('Account not found', 'error')
        return redirect(url_for('monzo.index'))
        
    try:
        monzo_repo.refresh_account_data(account)
        flash('Account data refreshed successfully', 'success')
    except Exception as e:
        log.error(f"Error refreshing account: {str(e)}")
        flash(f'Error refreshing account: {str(e)}', 'error')
        
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/accounts/<account_id>/toggle', methods=['POST'])
@login_required
def toggle_account(account_id):
    """Toggle account sync enabled/disabled."""
    account = monzo_repo.get_account_by_id(account_id)
    
    if not account or account.user_id != current_user.id:
        flash('Account not found', 'error')
        return redirect(url_for('monzo.index'))
        
    account.sync_enabled = not account.sync_enabled
    monzo_repo.save_account(account)
    
    status = 'enabled' if account.sync_enabled else 'disabled'
    flash(f'Sync {status} for account {account.name}', 'success')
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/accounts/<account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    """Delete a Monzo account."""
    account = monzo_repo.get_account_by_id(account_id)
    
    if not account or account.user_id != current_user.id:
        flash('Account not found', 'error')
        return redirect(url_for('monzo.index'))
    
    # Delete associated rules first
    rules = db.session.query(SyncRule).filter_by(source_account_id=account_id).all()
    for rule in rules:
        db.session.delete(rule)
    
    # Delete the account
    monzo_repo.delete_account(account)
    flash(f'Account {account.name} deleted successfully', 'success')
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/rules/create', methods=['GET', 'POST'])
@login_required
def create_rule():
    """Create a new sync rule."""
    # Get user's accounts and pots for the form
    accounts = monzo_repo.get_accounts_by_user_id(current_user.id)
    all_pots = []
    for account in accounts:
        pots = monzo_repo.get_pots_by_account_id(account.id)
        all_pots.extend(pots)
    
    if request.method == 'POST':
        name = request.form.get('name')
        source_account_id = request.form.get('source_account_id')
        target_pot_id = request.form.get('target_pot_id')
        trigger = request.form.get('trigger', 'cc_payment_due')
        action = request.form.get('action', 'transfer_full_balance')
        
        # Validate inputs
        if not name or not source_account_id or not target_pot_id:
            flash('All fields are required', 'error')
            return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)
            
        # Validate account ownership
        account = monzo_repo.get_account_by_id(source_account_id)
        pot = monzo_repo.get_pot_by_id(target_pot_id)
        
        if not account or account.user_id != current_user.id:
            flash('Invalid account selected', 'error')
            return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)
            
        if not pot:
            flash('Invalid pot selected', 'error')
            return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)
        
        # Parse action parameters
        action_params = {}
        if action == 'transfer_amount':
            amount = request.form.get('amount', 0)
            try:
                action_params['amount'] = int(float(amount) * 100)  # Convert to pence
            except ValueError:
                flash('Invalid amount', 'error')
                return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)
                
        elif action == 'transfer_percentage':
            percentage = request.form.get('percentage', 0)
            try:
                action_params['percentage'] = float(percentage)
            except ValueError:
                flash('Invalid percentage', 'error')
                return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)
        
        # Create the rule
        rule = SyncRule(
            user_id=current_user.id,
            name=name,
            source_account_id=source_account_id,
            target_pot_id=target_pot_id,
            trigger=trigger,
            action=action,
            action_params=json.dumps(action_params),
            is_active=True
        )
        
        db.session.add(rule)
        db.session.commit()
        
        flash('Sync rule created successfully', 'success')
        return redirect(url_for('monzo.index'))
        
    return render_template('monzo/create_rule.html', accounts=accounts, pots=all_pots)

@monzo_bp.route('/rules/<rule_id>/toggle', methods=['POST'])
@login_required
def toggle_rule(rule_id):
    """Toggle rule active/inactive."""
    rule = db.session.query(SyncRule).filter_by(id=rule_id).first()
    
    if not rule or rule.user_id != current_user.id:
        flash('Rule not found', 'error')
        return redirect(url_for('monzo.index'))
        
    rule.is_active = not rule.is_active
    db.session.commit()
    
    status = 'activated' if rule.is_active else 'deactivated'
    flash(f'Rule "{rule.name}" {status}', 'success')
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/rules/<rule_id>/delete', methods=['POST'])
@login_required
def delete_rule(rule_id):
    """Delete a sync rule."""
    rule = db.session.query(SyncRule).filter_by(id=rule_id).first()
    
    if not rule or rule.user_id != current_user.id:
        flash('Rule not found', 'error')
        return redirect(url_for('monzo.index'))
        
    db.session.delete(rule)
    db.session.commit()
    
    flash(f'Rule "{rule.name}" deleted successfully', 'success')
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/rules/<rule_id>/run', methods=['POST'])
@login_required
def run_rule(rule_id):
    """Manually run a sync rule."""
    rule = db.session.query(SyncRule).filter_by(id=rule_id).first()
    
    if not rule or rule.user_id != current_user.id:
        flash('Rule not found', 'error')
        return redirect(url_for('monzo.index'))
        
    try:
        sync = SyncService(monzo_repo)
        result = sync.sync_credit_card_balance(rule.id)
        
        if result:
            flash(f'Sync successful: {result.details}', 'success')
        else:
            flash('Sync completed but no transfer was needed', 'info')
            
    except Exception as e:
        log.error(f"Error running sync rule: {str(e)}")
        flash(f'Error running sync rule: {str(e)}', 'error')
        
    return redirect(url_for('monzo.index'))

@monzo_bp.route('/transactions/<account_id>')
@login_required
def transactions(account_id):
    """View account transactions."""
    account = monzo_repo.get_account_by_id(account_id)
    
    if not account or account.user_id != current_user.id:
        flash('Account not found', 'error')
        return redirect(url_for('monzo.index'))
        
    # Get transactions for the account
    transactions = monzo_repo.get_transactions_by_account_id(account_id, limit=50)
    
    return render_template(
        'monzo/transactions.html',
        account=account,
        transactions=transactions
    )
