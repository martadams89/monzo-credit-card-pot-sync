import logging
import json
import uuid
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.monzo import MonzoAccount, MonzoPot, MonzoTransaction, SyncRule, SyncHistory
from app.services.monzo_api import MonzoAPI, MonzoAPIError

log = logging.getLogger(__name__)

class MonzoRepository:
    """Repository for Monzo related database operations."""
    
    def __init__(self, db_session=None):
        self._session = db_session or db.session
    
    # Account methods
    def get_accounts_by_user_id(self, user_id):
        """Get all Monzo accounts for a user."""
        return MonzoAccount.query.filter_by(user_id=user_id).all()
    
    def get_account_by_id(self, account_id):
        """Get a Monzo account by ID."""
        return MonzoAccount.query.filter_by(id=account_id).first()
    
    def get_account_by_monzo_id(self, monzo_account_id):
        """Get a Monzo account by Monzo's account ID."""
        return MonzoAccount.query.filter_by(account_id=monzo_account_id).first()
    
    def save_account(self, account):
        """Save or update a Monzo account."""
        try:
            # If it's a new account
            if not account.id:
                account.id = str(uuid.uuid4())
            
            self._session.add(account)
            self._session.commit()
            return account
        except Exception as e:
            self._session.rollback()
            log.error(f"Error saving account: {str(e)}")
            raise
    
    def delete_account(self, account):
        """Delete a Monzo account."""
        try:
            # Delete related pots
            MonzoPot.query.filter_by(account_id=account.id).delete()
            
            # Delete related sync rules
            SyncRule.query.filter_by(source_account_id=account.id).delete()
            
            # Delete the account
            self._session.delete(account)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            log.error(f"Error deleting account: {str(e)}")
            raise
    
    def refresh_account_data(self, account):
        """Refresh account data from the Monzo API."""
        from app.services.monzo_api import MonzoAPI
        
        try:
            api = MonzoAPI(account.access_token)
            
            # Get basic account info if we don't have it
            if not account.account_id:
                accounts = api.get_accounts()
                uk_accounts = [acc for acc in accounts if acc.get('type') == 'uk_retail']
                if uk_accounts:
                    account.account_id = uk_accounts[0]['id']
                    account.name = uk_accounts[0].get('description', 'Monzo Account')
            
            # Get balance
            if account.account_id:
                balance_data = api.get_balance(account.account_id)
                account.balance = balance_data.get('balance', 0)
                account.currency = balance_data.get('currency', 'GBP')
            
            # Get pots
            pots_data = api.get_pots()
            
            # Update existing pots and add new ones
            for pot_data in pots_data:
                if pot_data.get('deleted', False):
                    continue
                    
                pot = MonzoPot.query.filter_by(pot_id=pot_data['id']).first()
                
                if not pot:
                    pot = MonzoPot(
                        id=str(uuid.uuid4()),
                        account_id=account.id,
                        pot_id=pot_data['id'],
                        name=pot_data['name'],
                        balance=pot_data['balance'],
                        currency=pot_data['currency'],
                        is_locked=pot_data.get('locked', False),
                        created_at=datetime.utcnow()
                    )
                else:
                    pot.name = pot_data['name']
                    pot.balance = pot_data['balance']
                    pot.currency = pot_data['currency']
                    pot.is_locked = pot_data.get('locked', False)
                    pot.updated_at = datetime.utcnow()
                
                self._session.add(pot)
            
            # Update account timestamps
            account.last_refreshed = datetime.utcnow()
            account.updated_at = datetime.utcnow()
            
            self._session.add(account)
            self._session.commit()
            return True
        except Exception as e:
            self._session.rollback()
            log.error(f"Error refreshing account data: {str(e)}")
            raise
    
    # Pot methods
    def get_pots_by_account_id(self, account_id):
        """Get all pots for an account."""
        return MonzoPot.query.filter_by(account_id=account_id).all()
    
    def get_pot_by_id(self, pot_id):
        """Get a pot by ID."""
        return MonzoPot.query.filter_by(id=pot_id).first()
    
    def get_pot_by_monzo_id(self, monzo_pot_id):
        """Get a pot by Monzo's pot ID."""
        return MonzoPot.query.filter_by(pot_id=monzo_pot_id).first()
    
    def save_pot(self, pot):
        """Save or update a pot."""
        try:
            # If it's a new pot
            if not pot.id:
                pot.id = str(uuid.uuid4())
            
            self._session.add(pot)
            self._session.commit()
            return pot
        except Exception as e:
            self._session.rollback()
            log.error(f"Error saving pot: {str(e)}")
            raise
    
    # Sync rule methods
    def get_rules_by_user_id(self, user_id):
        """Get all sync rules for a user."""
        return SyncRule.query.filter_by(user_id=user_id).all()
    
    def get_active_rules(self):
        """Get all active sync rules."""
        return SyncRule.query.filter_by(is_active=True).all()
    
    def get_daily_rules(self):
        """Get all active daily sync rules."""
        return SyncRule.query.filter_by(
            is_active=True,
            trigger_type='daily'
        ).all()
    
    def get_rule_by_id(self, rule_id):
        """Get a sync rule by ID."""
        return SyncRule.query.filter_by(id=rule_id).first()
    
    def save_rule(self, rule):
        """Save or update a sync rule."""
        try:
            # If it's a new rule
            if not rule.id:
                rule.id = str(uuid.uuid4())
            
            self._session.add(rule)
            self._session.commit()
            return rule
        except Exception as e:
            self._session.rollback()
            log.error(f"Error saving rule: {str(e)}")
            raise
    
    def delete_rule(self, rule):
        """Delete a sync rule."""
        try:
            self._session.delete(rule)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            log.error(f"Error deleting rule: {str(e)}")
            raise
    
    # Sync history methods
    def add_sync_history(self, user_id, source_account_id, target_pot_id, 
                         amount, currency='GBP', status='success', details=None, rule_id=None):
        """Add a sync history entry."""
        try:
            history = SyncHistory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                source_account_id=source_account_id,
                target_pot_id=target_pot_id,
                rule_id=rule_id,
                amount=amount,
                currency=currency,
                status=status,
                details=details,
                created_at=datetime.utcnow()
            )
            
            self._session.add(history)
            self._session.commit()
            return history
        except Exception as e:
            self._session.rollback()
            log.error(f"Error adding sync history: {str(e)}")
            raise
    
    def get_history_by_user_id(self, user_id, limit=50):
        """Get sync history for a user."""
        return SyncHistory.query.filter_by(user_id=user_id).order_by(
            SyncHistory.created_at.desc()
        ).limit(limit).all()
    
    def get_history_by_rule_id(self, rule_id, limit=50):
        """Get sync history for a rule."""
        return SyncHistory.query.filter_by(rule_id=rule_id).order_by(
            SyncHistory.created_at.desc()
        ).limit(limit).all()
