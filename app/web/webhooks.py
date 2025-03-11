import logging
import hmac
import hashlib
import json
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

from app.extensions import db
from app.models.monzo import MonzoAccount, MonzoPot, SyncRule
from app.models.monzo_repository import MonzoRepository
from app.services.sync_service import SyncService
from app.services.monzo_api import MonzoAPIService

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")
log = logging.getLogger(__name__)

# Initialize repositories and services
monzo_repository = MonzoRepository(db)
monzo_api_service = MonzoAPIService()
sync_service = SyncService(monzo_repository, monzo_api_service)

@webhooks_bp.route("/monzo", methods=["POST"])
def monzo_webhook():
    """Handle incoming Monzo webhooks."""
    # Verify webhook signature if configured
    webhook_secret = current_app.config.get('MONZO_WEBHOOK_SECRET')
    if webhook_secret:
        signature = request.headers.get('X-Monzo-Signature')
        if not signature:
            log.warning("Missing Monzo webhook signature")
            return jsonify({"status": "error", "message": "Missing signature"}), 401
        
        # Compute HMAC signature
        expected_signature = hmac.new(
            webhook_secret.encode(),
            request.get_data(),
            hashlib.sha256
        ).hexdigest()
        
        # Secure comparison to prevent timing attacks
        if not hmac.compare_digest(signature, expected_signature):
            log.warning("Invalid Monzo webhook signature")
            return jsonify({"status": "error", "message": "Invalid signature"}), 401
    
    # Parse webhook data
    try:
        data = request.json
        
        # Log webhook type
        webhook_type = data.get('type')
        log.info(f"Received Monzo webhook: {webhook_type}")
        
        # Handle different webhook types
        if webhook_type == 'transaction.created':
            return handle_transaction_created(data)
        elif webhook_type == 'balance.changed':
            return handle_balance_changed(data)
        else:
            # Acknowledge receipt but take no action
            log.info(f"Ignored webhook type: {webhook_type}")
            return jsonify({"status": "ok", "message": "Webhook received but not processed"}), 200
            
    except Exception as e:
        log.error(f"Error processing Monzo webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def handle_transaction_created(data):
    """Handle transaction.created webhook."""
    try:
        # Extract relevant data from the webhook
        transaction_data = data.get('data')
        if not transaction_data:
            return jsonify({"status": "error", "message": "No transaction data"}), 400
        
        account_id = transaction_data.get('account_id')
        if not account_id:
            return jsonify({"status": "error", "message": "No account ID in transaction"}), 400
        
        # Find the corresponding Monzo account in our database
        monzo_account = db.session.query(MonzoAccount).filter_by(account_id=account_id).first()
        if not monzo_account:
            log.warning(f"Transaction webhook received for unknown account ID: {account_id}")
            return jsonify({"status": "error", "message": "Unknown account ID"}), 404
        
        # Only process if the account has sync enabled
        if not monzo_account.sync_enabled:
            log.info(f"Sync disabled for account {monzo_account.id}, ignoring transaction webhook")
            return jsonify({"status": "ok", "message": "Sync disabled for account"}), 200
        
        # Find any rules that should trigger on balance changes
        rules = db.session.query(SyncRule).filter_by(
            source_account_id=monzo_account.id,
            trigger_type='balance_change',
            is_active=True
        ).all()
        
        results = []
        for rule in rules:
            # Execute the rule
            result = sync_service.execute_rule(rule.id)
            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "result": result
            })
        
        return jsonify({
            "status": "ok", 
            "message": "Transaction processed",
            "results": results
        }), 200
        
    except Exception as e:
        log.error(f"Error handling transaction.created webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def handle_balance_changed(data):
    """Handle balance.changed webhook."""
    try:
        # Extract relevant data from the webhook
        balance_data = data.get('data')
        if not balance_data:
            return jsonify({"status": "error", "message": "No balance data"}), 400
        
        account_id = balance_data.get('account_id')
        if not account_id:
            return jsonify({"status": "error", "message": "No account ID in balance data"}), 400
        
        # Find the corresponding Monzo account in our database
        monzo_account = db.session.query(MonzoAccount).filter_by(account_id=account_id).first()
        if not monzo_account:
            log.warning(f"Balance webhook received for unknown account ID: {account_id}")
            return jsonify({"status": "error", "message": "Unknown account ID"}), 404
        
        # Update the stored balance
        new_balance = balance_data.get('balance')
        if new_balance is not None:  # Check if balance is provided (could be 0)
            monzo_account.balance = new_balance
            monzo_account.last_refreshed = datetime.utcnow()
            db.session.commit()
        
        # Only process if the account has sync enabled
        if not monzo_account.sync_enabled:
            log.info(f"Sync disabled for account {monzo_account.id}, ignoring balance webhook")
            return jsonify({"status": "ok", "message": "Sync disabled for account"}), 200
        
        # Find any rules that should trigger on balance changes
        rules = db.session.query(SyncRule).filter_by(
            source_account_id=monzo_account.id,
            trigger_type='balance_change',
            is_active=True
        ).all()
        
        results = []
        for rule in rules:
            # Execute the rule
            result = sync_service.execute_rule(rule.id)
            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "result": result
            })
        
        return jsonify({
            "status": "ok", 
            "message": "Balance change processed",
            "results": results
        }), 200
        
    except Exception as e:
        log.error(f"Error handling balance.changed webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
