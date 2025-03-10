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
    """Repository for Monzo accounts and related data."""
    
    def __init__(self, db_session=None):
        self._session = db_session or db.session
    
    def get_account_by_id(self, account_id: str) -> Optional<MonzoAccount]:
        """Get a Monzo account by ID."""
        return self._session.query(MonzoAccount).filter_by(id=account_id).one_or_none()
    
    def get_accounts_by_user_id(self, user_id: str) -> List<MonzoAccount]:
        """Get all Monzo accounts for a user."""
        return self._session.query(MonzoAccount).filter_by(user_id=user_id).all()
    
    def get_active_accounts(self) -> List<MonzoAccount]:
        """Get all active accounts."""
        return self._session.query(MonzoAccount).filter_by(is_active=True).all()
    
    def save_account(self, account: MonzoAccount) -> MonzoAccount:
        """Save or update a Monzo account."""
        try:
            self._session.add(account)
            self._session.commit()
            return account
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error saving account: {str(e)}")
            raise
    
    def delete_account(self, account: MonzoAccount) -> None:
        """Delete a Monzo account."""
        try:
            self._session.delete(account)
            self._session.commit()
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error deleting account: {str(e)}")
            raise
    
    def get_pot_by_id(self, pot_id: str) -> Optional[MonzoPot]:
        """Get a pot by ID."""
        return self._session.query(MonzoPot).filter_by(id=pot_id).one_or_none()
    
    def get_pots_by_account_id(self, account_id: str) -> List<MonzoPot]:
        """Get all pots for an account."""
        return self._session.query(MonzoPot).filter_by(account_id=account_id).all()
    
    def save_pot(self, pot: MonzoPot) -> MonzoPot:
        """Save or update a pot."""
        try:
            self._session.add(pot)
            self._session.commit()
            return pot
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error saving pot: {str(e)}")
            raise
    
    def update_pots_from_api(self, account: MonzoAccount) -> List<MonzoPot]:
        """Fetch and update pots from the Monzo API."""
        try:
            api = MonzoAPI(account.access_token)
            api_pots = api.get_pots(account.id)
            
            saved_pots = []
            for api_pot in api_pots:
                # Skip deleted pots
                if api_pot.get("deleted", False):
                    continue
                    
                pot = self.get_pot_by_id(api_pot["id"])
                if not pot:
                    # Create new pot
                    pot = MonzoPot(
                        id=api_pot["id"],
                        account_id=account.id,
                        name=api_pot["name"],
                        style=api_pot.get("style"),
                        balance=api_pot["balance"],
                        goal_amount=api_pot.get("goal_amount"),
                        is_locked=api_pot.get("locked", False),
                        created_at=datetime.fromisoformat(api_pot["created"].replace('Z', '+00:00')),
                        updated_at=datetime.utcnow(),
                        raw_data=json.dumps(api_pot)
                    )
                else:
                    # Update existing pot
                    pot.name = api_pot["name"]
                    pot.style = api_pot.get("style")
                    pot.balance = api_pot["balance"]
                    pot.goal_amount = api_pot["goal_amount"]
                    pot.is_locked = api_pot.get("locked", False)
                    pot.updated_at = datetime.utcnow()
                    pot.raw_data = json.dumps(api_pot)
                
                saved_pots.append(self.save_pot(pot))
            
            return saved_pots
        except (MonzoAPIError, SQLAlchemyError) as e:
            log.error(f"Error updating pots from API: {str(e)}")
            raise
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[MonzoTransaction]:
        """Get a transaction by ID."""
        return self._session.query(MonzoTransaction).filter_by(id=transaction_id).one_or_none()
    
    def get_transactions_by_account_id(
        self, 
        account_id: str,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[MonzoTransaction]:
        """Get transactions for an account."""
        query = self._session.query(MonzoTransaction).filter_by(account_id=account_id)
        
        if since:
            query = query.filter(MonzoTransaction.created_at >= since)
            
        return query.order_by(MonzoTransaction.created_at.desc()).limit(limit).all()
    
    def save_transaction(self, transaction: MonzoTransaction) -> MonzoTransaction:
        """Save or update a transaction."""
        try:
            self._session.add(transaction)
            self._session.commit()
            return transaction
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error saving transaction: {str(e)}")
            raise
    
    def update_transactions_from_api(
        self, 
        account: MonzoAccount, 
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MonzoTransaction]:
        """Fetch and update transactions from the Monzo API."""
        try:
            if not since:
                # Default to last 24 hours if not specified
                since = datetime.utcnow() - timedelta(days=1)
                
            api = MonzoAPI(account.access_token)
            api_transactions = api.get_transactions(account.id, since=since, limit=limit)
            
            saved_transactions = []
            for api_tx in api_transactions:
                # Skip declined transactions
                if api_tx.get("declined", False):
                    continue
                
                tx = self.get_transaction_by_id(api_tx["id"])
                
                # Extract merchant data if available
                merchant_data = api_tx.get("merchant", {})
                merchant_name = merchant_data.get("name") if merchant_data else None
                merchant_logo = merchant_data.get("logo") if merchant_data else None
                merchant_category = merchant_data.get("category") if merchant_data else None
                
                if not tx:
                    # Create new transaction
                    tx = MonzoTransaction(
                        id=api_tx["id"],
                        account_id=account.id,
                        amount=api_tx["amount"],
                        description=api_tx.get("description", ""),
                        currency=api_tx.get("currency", "GBP"),
                        merchant_name=merchant_name,
                        merchant_logo=merchant_logo,
                        merchant_category=merchant_category,
                        categories=json.dumps(api_tx.get("categories", {})),
                        notes=api_tx.get("notes", ""),
                        metadata=json.dumps(api_tx.get("metadata", {})),
                        is_load=api_tx.get("is_load", False),
                        settled=api_tx.get("settled", ""),
                        local_amount=api_tx.get("local_amount"),
                        local_currency=api_tx.get("local_currency"),
                        updated_at=datetime.utcnow(),
                        created_at=datetime.fromisoformat(api_tx["created"].replace('Z', '+00:00')),
                        raw_data=json.dumps(api_tx)
                    )
                else:
                    # Update existing transaction (some fields may change after settlement)
                    tx.amount = api_tx["amount"]
                    tx.description = api_tx.get("description", "")
                    tx.merchant_name = merchant_name
                    tx.merchant_logo = merchant_logo
                    tx.merchant_category = merchant_category
                    tx.categories = json.dumps(api_tx.get("categories", {}))
                    tx.notes = api_tx.get("notes", "")
                    tx.metadata = json.dumps(api_tx.get("metadata", {}))
                    tx.settled = api_tx.get("settled", "")
                    tx.updated_at = datetime.utcnow()
                    tx.raw_data = json.dumps(api_tx)
                
                saved_transactions.append(self.save_transaction(tx))
            
            return saved_transactions
        except (MonzoAPIError, SQLAlchemyError) as e:
            log.error(f"Error updating transactions from API: {str(e)}")
            raise
    
    def refresh_account_data(self, account: MonzoAccount) -> Tuple[MonzoAccount, List[MonzoPot], List[MonzoTransaction]]:
        """Refresh all data for an account."""
        try:
            api = MonzoAPI(account.access_token)
            
            # Get account balance
            balance_data = api.get_balance(account.id)
            account.balance = balance_data.get("balance", 0)
            account.total_balance = balance_data.get("total_balance", 0)
            account.currency = balance_data.get("currency", "GBP")
            account.last_refreshed = datetime.utcnow()
            self.save_account(account)
            
            # Update pots
            pots = self.update_pots_from_api(account)
            
            # Update recent transactions
            since = datetime.utcnow() - timedelta(days=7)  # Last 7 days
            transactions = self.update_transactions_from_api(account, since=since)
            
            return account, pots, transactions
        except Exception as e:
            log.error(f"Error refreshing account data: {str(e)}")
            raise
    
    # Sync rule methods
    def get_rule_by_id(self, rule_id: str) -> Optional[SyncRule]:
        """Get a sync rule by ID."""
        return self._session.query(SyncRule).filter_by(id=rule_id).one_or_none()
    
    def get_rules_by_user_id(self, user_id: str) -> List[SyncRule]:
        """Get all sync rules for a user."""
        return self._session.query(SyncRule).filter_by(user_id=user_id).all()
    
    def get_active_rules_by_user_id(self, user_id: str) -> List[SyncRule]:
        """Get active sync rules for a user."""
        return self._session.query(SyncRule).filter_by(user_id=user_id, is_active=True).all()
    
    def save_rule(self, rule: SyncRule) -> SyncRule:
        """Save or update a sync rule."""
        try:
            self._session.add(rule)
            self._session.commit()
            return rule
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error saving sync rule: {str(e)}")
            raise
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a sync rule."""
        try:
            rule = self.get_rule_by_id(rule_id)
            if rule:
                self._session.delete(rule)
                self._session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error deleting sync rule: {str(e)}")
            raise
    
    # Sync history methods
    def add_sync_history(self, history: SyncHistory) -> SyncHistory:
        """Add a new sync history entry."""
        try:
            self._session.add(history)
            self._session.commit()
            return history
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error adding sync history: {str(e)}")
            raise
    
    def get_sync_history_by_user_id(self, user_id: str, limit: int = 10) -> List[SyncHistory]:
        """Get recent sync history for a user."""
        return (self._session.query(SyncHistory)
                .filter_by(user_id=user_id)
                .order_by(SyncHistory.created_at.desc())
                .limit(limit)
                .all())
