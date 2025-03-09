"""Routes for account management."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import current_user, login_required
from app.extensions import db
from app.services.container import container
from app.models.account import Account
from datetime import datetime

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/')
@login_required
def index():
    """Accounts overview page."""
    return redirect(url_for('accounts.manage'))

@accounts_bp.route('/manage')
@login_required
def manage():
    """Manage accounts page."""
    monzo_accounts = Account.query.filter_by(user_id=current_user.id, type='monzo').all()
    credit_card_accounts = Account.query.filter_by(user_id=current_user.id, type='credit_card').all()
    
    return render_template('accounts/manage.html', 
                          title='Manage Accounts',
                          monzo_accounts=monzo_accounts, 
                          credit_card_accounts=credit_card_accounts)

@accounts_bp.route('/connect')
@login_required
def connect():
    """Connect a new account page."""
    return render_template('accounts/connect.html', title='Connect Account')

@accounts_bp.route('/connect/monzo')
@login_required
def connect_monzo():
    """Connect a Monzo account."""
    # Get the auth service
    auth_service = container().get('auth_service')
    
    if not auth_service:
        flash('Monzo integration is not available at this time.', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Get authorization URL
    auth_url = auth_service.get_monzo_auth_url(current_user.id)
    
    if not auth_url:
        flash('Error generating Monzo authorization URL.', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Redirect to Monzo auth page
    return redirect(auth_url)

@accounts_bp.route('/connect/credit-card')
@login_required
def connect_credit_card():
    """Connect a credit card account."""
    # Get the TrueLayer auth service for credit cards
    auth_service = container().get('auth_service')
    
    if not auth_service:
        flash('Credit card integration is not available at this time.', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Get authorization URL
    auth_url = auth_service.get_truelayer_auth_url(current_user.id)
    
    if not auth_url:
        flash('Error generating credit card authorization URL.', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Redirect to TrueLayer auth page
    return redirect(auth_url)

@accounts_bp.route('/pots')
@login_required
def pots():
    """Manage pots and their mappings."""
    # Get accounts
    monzo_accounts = Account.query.filter_by(user_id=current_user.id, type='monzo').all()
    credit_card_accounts = Account.query.filter_by(user_id=current_user.id, type='credit_card').all()
    
    if not monzo_accounts:
        flash('You need to connect a Monzo account first.', 'info')
        return redirect(url_for('accounts.connect'))
    
    if not credit_card_accounts:
        flash('You need to connect at least one credit card to map to pots.', 'info')
        return redirect(url_for('accounts.connect'))
    
    # Get pot mappings
    pot_service = container().get('pot_service')
    pot_mappings = pot_service.get_pot_mappings(current_user.id) if pot_service else []
    
    return render_template('accounts/pots.html', 
                          title='Manage Pots',
                          monzo_accounts=monzo_accounts,
                          credit_card_accounts=credit_card_accounts,
                          pot_mappings=pot_mappings)

@accounts_bp.route('/pots/update', methods=['POST'])
@login_required
def update_pot_mappings():
    """Update pot mappings between credit cards and pots."""
    # Get mapping data from form
    mappings = {}
    for key, value in request.form.items():
        if key.startswith('mappings[') and key.endswith(']'):
            card_id = key[9:-1]  # Extract the card ID from the form key
            mappings[card_id] = value if value else None
    
    # Get pot service from container
    pot_service = container().get('pot_service')
    if not pot_service:
        flash('Pot service is not available', 'error')
        return redirect(url_for('accounts.pots'))
    
    # Update mappings
    try:
        pot_service.update_pot_mappings(current_user.id, mappings)
        flash('Pot mappings updated successfully!', 'success')
    except Exception as e:
        current_app.logger.error(f"Error updating pot mappings: {str(e)}")
        flash(f'Error updating pot mappings: {str(e)}', 'error')
    
    return redirect(url_for('accounts.pots'))

@accounts_bp.route('/refresh/<account_id>', methods=['POST'])
@login_required
def refresh_account(account_id):
    """Refresh an account's data."""
    # Check if the account belongs to the current user
    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
    
    if not account:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    
    # Get the appropriate service based on account type
    if account.type == 'monzo':
        service = container().get('monzo_service')
    elif account.type == 'credit_card':
        service = container().get('truelayer_service')
    else:
        return jsonify({'success': False, 'message': 'Unknown account type'}), 400
    
    if not service:
        return jsonify({'success': False, 'message': 'Service not available'}), 503
    
    try:
        # Refresh the account
        success = service.refresh_account(account)
        
        if success:
            # Update last_synced_at timestamp
            account.last_synced_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Failed to refresh account'}), 500
    except Exception as e:
        current_app.logger.error(f"Error refreshing account: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@accounts_bp.route('/delete/<account_id>', methods=['POST'])
@login_required
def delete_account(account_id):
    """Delete an account."""
    # Check if the account belongs to the current user
    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
    
    if not account:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    
    try:
        # Delete any pot mappings first
        pot_service = container().get('pot_service')
        if pot_service:
            pot_service.remove_account_mappings(account_id)
        
        # Delete the account
        db.session.delete(account)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting account: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
