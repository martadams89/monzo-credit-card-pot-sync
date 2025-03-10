import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.api_key import ApiKey
from app.models.monzo import MonzoAccount, MonzoPot, SyncRule, SyncHistory
from app.services.sync_service import SyncService
from app.services.monzo_api import MonzoAPIService
from app.models.monzo_repository import MonzoRepository
from app.utils.notifications import send_notification

api_bp = Blueprint("api", __name__, url_prefix="/api")
log = logging.getLogger(__name__)

def api_key_required(f):
    """Decorator to check for valid API key in request."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({"error": "API key is required"}), 401
        
        # Check if API key exists and is active
        key = ApiKey.query.filter_by(key_hash=generate_password_hash(api_key), is_active=True).first()
        
        if not key:
            return jsonify({"error": "Invalid API key"}), 401
            
        # Check if API key is expired
        if key.expires_at and key.expires_at < datetime.utcnow():
            return jsonify({"error": "API key has expired"}), 401
        
        # Update last used timestamp
        key.update_last_used()
        db.session.commit()
        
        # Add the user to the request context
        request.user = key.user
        
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "version": current_app.config.get("VERSION", "1.0.0"),
        "timestamp": datetime.utcnow().isoformat()
    })

@api_bp.route("/accounts", methods=["GET"])
@api_key_required
def get_accounts():
    """Get all Monzo accounts for the authenticated user."""
    accounts = MonzoAccount.query.filter_by(user_id=request.user.id).all()
    
    return jsonify({
        "accounts": [
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "account_id": account.account_id,
                "is_active": account.is_active,
                "sync_enabled": account.sync_enabled,
                "balance": account.balance,
                "currency": account.currency,
                "last_refreshed": account.last_refreshed.isoformat() if account.last_refreshed else None
            }
            for account in accounts
        ]
    })

@api_bp.route("/accounts/<account_id>", methods=["GET"])
@api_key_required
def get_account(account_id):
    """Get details for a specific Monzo account."""
    account = MonzoAccount.query.filter_by(id=account_id, user_id=request.user.id).first_or_404()
    
    # Get pots for this account
    pots = MonzoPot.query.filter_by(account_id=account_id).all()
    
    return jsonify({
        "account": {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "account_id": account.account_id,
            "is_active": account.is_active,
            "sync_enabled": account.sync_enabled,
            "balance": account.balance,
            "currency": account.currency,
            "last_refreshed": account.last_refreshed.isoformat() if account.last_refreshed else None,
            "pots": [
                {
                    "id": pot.id,
                    "name": pot.name,
                    "pot_id": pot.pot_id,
                    "balance": pot.balance,
                    "currency": pot.currency,
                    "is_locked": pot.is_locked
                }
                for pot in pots
            ]
        }
    })

@api_bp.route("/accounts/<account_id>/refresh", methods=["POST"])
@api_key_required
def refresh_account(account_id):
    """Refresh account and pot data from Monzo API."""
    account = MonzoAccount.query.filter_by(id=account_id, user_id=request.user.id).first_or_404()
    
    try:
        monzo_api = MonzoAPIService()
        monzo_repository = MonzoRepository(db)
        
        # Refresh the account data
        updated = monzo_repository.refresh_account_data(account)
        
        if updated:
            return jsonify({
                "status": "success",
                "message": "Account data refreshed successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to refresh account data"
            }), 500
            
    except Exception as e:
        log.error(f"Error refreshing account {account_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@api_bp.route("/rules", methods=["GET"])
@api_key_required
def get_rules():
    """Get all sync rules for the authenticated user."""
    rules = SyncRule.query.filter_by(user_id=request.user.id).all()
    
    return jsonify({
        "rules": [
            {
                "id": rule.id,
                "name": rule.name,
                "source_account_id": rule.source_account_id,
                "target_pot_id": rule.target_pot_id,
                "trigger_type": rule.trigger_type,
                "action_type": rule.action_type,
                "action_amount": rule.action_amount,
                "action_percentage": rule.action_percentage,
                "is_active": rule.is_active,
                "last_run_at": rule.last_run_at.isoformat() if rule.last_run_at else None
            }
            for rule in rules
        ]
    })

@api_bp.route("/rules/<rule_id>/execute", methods=["POST"])
@api_key_required
def execute_rule(rule_id):
    """Manually execute a specific sync rule."""
    rule = SyncRule.query.filter_by(id=rule_id, user_id=request.user.id).first_or_404()
    
    if not rule.is_active:
        return jsonify({
            "status": "error",
            "message": "Rule is not active"
        }), 400
    
    try:
        # Set up services
        monzo_api = MonzoAPIService()
        monzo_repository = MonzoRepository(db)
        sync_service = SyncService(monzo_repository, monzo_api)
        
        # Execute the rule
        result = sync_service.execute_rule(rule)
        
        # Update the rule's last run timestamp
        rule.last_run_at = datetime.utcnow()
        db.session.commit()
        
        if result.get("success"):
            # Add to sync history
            history = SyncHistory(
                id=str(uuid.uuid4()),
                user_id=request.user.id,
                rule_id=rule_id,
                amount=result.get("amount"),
                status="success",
                details=result.get("message"),
                created_at=datetime.utcnow()
            )
            db.session.add(history)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": result.get("message"),
                "amount": result.get("amount")
            })
        else:
            # Add to sync history
            history = SyncHistory(
                id=str(uuid.uuid4()),
                user_id=request.user.id,
                rule_id=rule_id,
                amount=0,
                status="error",
                details=result.get("error"),
                created_at=datetime.utcnow()
            )
            db.session.add(history)
            db.session.commit()
            
            return jsonify({
                "status": "error",
                "message": result.get("error")
            }), 400
            
    except Exception as e:
        log.error(f"Error executing rule {rule_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error: {str(e)}"
        }), 500

@api_bp.route("/history", methods=["GET"])
@api_key_required
def get_sync_history():
    """Get sync history for the authenticated user."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # Limit max per_page to 100
    
    history_query = SyncHistory.query.filter_by(user_id=request.user.id)
    
    # Apply filters
    rule_id = request.args.get('rule_id')
    if rule_id:
        history_query = history_query.filter_by(rule_id=rule_id)
    
    status = request.args.get('status')
    if status:
        history_query = history_query.filter_by(status=status)
    
    # Order by created_at (newest first)
    history_query = history_query.order_by(SyncHistory.created_at.desc())
    
    # Paginate results
    paginated_history = history_query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        "history": [
            {
                "id": entry.id,
                "rule_id": entry.rule_id,
                "amount": entry.amount,
                "status": entry.status,
                "details": entry.details,
                "created_at": entry.created_at.isoformat()
            }
            for entry in paginated_history.items
        ],
        "pagination": {
            "current_page": paginated_history.page,
            "total_pages": paginated_history.pages,
            "total_items": paginated_history.total,
            "per_page": paginated_history.per_page,
            "has_next": paginated_history.has_next,
            "has_prev": paginated_history.has_prev
        }
    })
