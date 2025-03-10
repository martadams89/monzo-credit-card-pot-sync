import logging
import json
import uuid
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from app.models.monzo import MonzoAccount, MonzoPot, SyncRule, SyncHistory
from app.models.monzo_repository import MonzoRepository
from app.services.monzo_api import MonzoAPI, MonzoAPIError
from app.extensions import db
from app.utils.notifications import send_notification

log = logging.getLogger(__name__)

class SyncService:
    """Service for syncing between accounts and pots."""
    
    def __init__(self, monzo_repository: MonzoRepository, monzo_api: MonzoAPIService):
        self.monzo_repository = monzo_repository
        self.monzo_api = monzo_api
    
    def execute_rule(self, rule_id: str) -> Dict[str, any]:
        """
        Execute a specific sync rule.
        
        Returns:
            Dict with status and details of the execution
        """
        # Get the rule
        rule = self.monzo_repository.get_rule_by_id(rule_id)
        if not rule:
            log.error(f"Rule not found: {rule_id}")
            return {"status": "error", "message": "Rule not found"}
        
        # Check if rule is active
        if not rule.is_active:
            log.warning(f"Rule {rule_id} is not active, skipping execution")
            return {"status": "skipped", "message": "Rule is not active"}
        
        # Get source account
        source_account = self.monzo_repository.get_account_by_id(rule.source_account_id)
        if not source_account:
            log.error(f"Source account not found: {rule.source_account_id}")
            return {"status": "error", "message": "Source account not found"}
        
        # Check if source account is active and sync enabled
        if not source_account.is_active or not source_account.sync_enabled:
            log.warning(f"Source account {rule.source_account_id} is not active or sync disabled")
            return {"status": "skipped", "message": "Source account is not active or sync disabled"}
        
        # Get target pot
        target_pot = self.monzo_repository.get_pot_by_id(rule.target_pot_id)
        if not target_pot:
            log.error(f"Target pot not found: {rule.target_pot_id}")
            return {"status": "error", "message": "Target pot not found"}
        
        # Ensure source account has a valid token
        try:
            # Refresh account data from Monzo API
            balance_info = self.monzo_api.get_balance(source_account)
            if not balance_info:
                log.error(f"Failed to get balance for account {source_account.id}")
                return {"status": "error", "message": "Failed to get balance for account"}
            
            # Get current balance from the response
            current_balance = balance_info.get('balance', 0)
            
            # Determine amount to transfer based on rule type
            amount_to_transfer = 0
            
            if rule.action_type == 'transfer_full_balance':
                amount_to_transfer = current_balance
            elif rule.action_type == 'transfer_amount' and rule.action_amount:
                amount_to_transfer = rule.action_amount
            elif rule.action_type == 'transfer_percentage' and rule.action_percentage:
                # Calculate percentage of the balance
                percentage = rule.action_percentage / 100
                amount_to_transfer = int(current_balance * percentage)
            else:
                log.error(f"Invalid rule action type or missing parameters: {rule.action_type}")
                return {"status": "error", "message": "Invalid rule action type or missing parameters"}
            
            # Skip if amount is 0 or negative
            if amount_to_transfer <= 0:
                log.info(f"Amount to transfer is {amount_to_transfer}, skipping")
                return {"status": "skipped", "message": "Amount to transfer is zero or negative"}
            
            # Execute the transfer
            success = self.monzo_api.deposit_to_pot(source_account, target_pot.pot_id, amount_to_transfer)
            
            if success:
                # Update pot balance
                target_pot.balance = target_pot.balance + amount_to_transfer
                self.monzo_repository.save_pot(target_pot)
                
                # Update rule last run time
                rule.last_run = datetime.utcnow()
                self.monzo_repository.save_rule(rule)
                
                # Record sync history
                history = SyncHistory(
                    id=str(uuid.uuid4()),
                    user_id=rule.user_id,
                    rule_id=rule.id,
                    amount=amount_to_transfer,
                    currency=source_account.currency,
                    source_account_id=source_account.id,
                    target_pot_id=target_pot.id,
                    status='success',
                    created_at=datetime.utcnow()
                )
                self.monzo_repository.add_sync_history(history)
                
                # Send notification (adjust as needed)
                send_notification(
                    user_id=rule.user_id,
                    title="Sync Completed",
                    message=f"Transferred {(amount_to_transfer/100):.2f} {source_account.currency} from {source_account.name} to {target_pot.name}",
                    notification_type="sync_success"
                )
                
                return {
                    "status": "success", 
                    "amount": amount_to_transfer,
                    "currency": source_account.currency,
                    "source_account": source_account.name,
                    "target_pot": target_pot.name
                }
            else:
                log.error(f"Failed to deposit to pot {target_pot.id}")
                
                # Record failed sync history
                history = SyncHistory(
                    id=str(uuid.uuid4()),
                    user_id=rule.user_id,
                    rule_id=rule.id,
                    amount=amount_to_transfer,
                    currency=source_account.currency,
                    source_account_id=source_account.id,
                    target_pot_id=target_pot.id,
                    status='failed',
                    error_details="API call to deposit to pot failed",
                    created_at=datetime.utcnow()
                )
                self.monzo_repository.add_sync_history(history)
                
                return {"status": "error", "message": "Failed to deposit to pot"}
            
        except Exception as e:
            log.error(f"Error executing rule {rule_id}: {str(e)}")
            
            # Record failed sync history
            history = SyncHistory(
                id=str(uuid.uuid4()),
                user_id=rule.user_id,
                rule_id=rule.id,
                amount=0,  # We don't know the amount at this point
                currency=source_account.currency,
                source_account_id=source_account.id,
                target_pot_id=target_pot.id,
                status='failed',
                error_details=str(e),
                created_at=datetime.utcnow()
            )
            self.monzo_repository.add_sync_history(history)
            
            return {"status": "error", "message": str(e)}
    
    def execute_daily_rules(self) -> Dict[str, any]:
        """Execute all daily sync rules."""
        # Get all active rules with trigger_type = 'daily'
        rules = db.session.query(SyncRule).filter_by(
            trigger_type='daily', 
            is_active=True
        ).all()
        
        results = {
            "total": len(rules),
            "success": 0,
            "error": 0,
            "skipped": 0,
            "details": []
        }
        
        for rule in rules:
            rule_result = self.execute_rule(rule.id)
            results["details"].append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "result": rule_result
            })
            
            if rule_result["status"] == "success":
                results["success"] += 1
            elif rule_result["status"] == "error":
                results["error"] += 1
            else:
                results["skipped"] += 1
        
        return results
    
    def execute_manual_sync(self, rule_id: str, user_id: str) -> Dict[str, any]:
        """Execute a manual sync for a specific rule and user."""
        # First, verify the rule belongs to the user
        rule = db.session.query(SyncRule).filter_by(
            id=rule_id,
            user_id=user_id
        ).first()
        
        if not rule:
            return {"status": "error", "message": "Rule not found or does not belong to user"}
        
        return self.execute_rule(rule_id)
