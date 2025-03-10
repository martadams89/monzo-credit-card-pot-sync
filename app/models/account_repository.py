from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import not_
from sqlalchemy.exc import NoResultFound
from typing import List, Optional
from datetime import datetime
import uuid
import logging
from sqlalchemy.exc import SQLAlchemyError

from app.domain.accounts import Account, MonzoAccount, TrueLayerAccount
from app.models.account import AccountModel

log = logging.getLogger(__name__)

class SqlAlchemyAccountRepository:
    """Repository for accounts using SQLAlchemy."""
    
    def __init__(self, db: SQLAlchemy) -> None:
        self._session = db.session

    def _to_model(self, account: Account) -> AccountModel:
        return AccountModel(
            type=account.type,
            access_token=account.access_token,
            refresh_token=account.refresh_token,
            token_expiry=account.token_expiry,
            pot_id=account.pot_id,
            account_id=account.account_id,
            cooldown_until=account.cooldown_until,
            prev_balance=account.prev_balance if isinstance(account.prev_balance, int) else 0,
            cooldown_ref_card_balance=account.cooldown_ref_card_balance,
            cooldown_ref_pot_balance=account.cooldown_ref_pot_balance,
            stable_pot_balance=account.stable_pot_balance
        )

    def _to_domain(self, model: AccountModel) -> Account:
        return Account(
            type=model.type,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expiry=model.token_expiry,
            pot_id=model.pot_id,
            account_id=model.account_id,
            cooldown_until=(int(model.cooldown_until) if model.cooldown_until is not None else None),
            prev_balance=model.prev_balance,
            cooldown_ref_card_balance=model.cooldown_ref_card_balance,
            cooldown_ref_pot_balance=model.cooldown_ref_pot_balance,
            stable_pot_balance=model.stable_pot_balance
        )

    def get_all(self) -> list[Account]:
        results: list[AccountModel] = self._session.query(AccountModel).all()
        return list(map(self._to_domain, results))

    def get_monzo_account(self) -> MonzoAccount:
        result: AccountModel = (
            self._session.query(AccountModel).filter_by(type="Monzo").one()
        )
        account = self._to_domain(result)
        return MonzoAccount(
            account.access_token,
            account.refresh_token,
            account.token_expiry,
            account.pot_id,
            account_id=account.account_id,
            prev_balance=account.prev_balance
        )

    def get_credit_accounts(self) -> list[TrueLayerAccount]:
        results: list[AccountModel] = (
            self._session.query(AccountModel)
            .filter(not_(AccountModel.type.contains("Monzo")))
            .all()
        )
        accounts = list(map(self._to_domain, results))
        return [
            TrueLayerAccount(
                a.type,
                a.access_token,
                a.refresh_token,
                a.token_expiry,
                a.pot_id,
                prev_balance=a.prev_balance,
                stable_pot_balance=a.stable_pot_balance
            )
            for a in accounts
        ]

    def get(self, type: str) -> Account:
        result: AccountModel = (
            self._session.query(AccountModel).filter_by(type=type).one_or_none()
        )
        if result is None:
            # Log the issue and handle gracefully
            raise NoResultFound(f"Account with type '{type}' not found.")
        return self._to_domain(result)

    def save(self, account: Account) -> None:
        # Check if an account with the same type exists
        existing = self._session.query(AccountModel).filter_by(type=account.type).one_or_none()
        if existing:
            # Update existing record
            existing.access_token = account.access_token
            existing.refresh_token = account.refresh_token
            existing.token_expiry = account.token_expiry
            existing.pot_id = account.pot_id
            existing.account_id = account.account_id
            existing.prev_balance = account.prev_balance
            # Only overwrite the cooldown fields if the domain object is explicitly setting them
            if account.cooldown_until is not None:
                existing.cooldown_until = account.cooldown_until
            # If needed, do the same for cooldown_ref_card_balance or others:
            # if account.cooldown_ref_card_balance is not None:
            #     existing.cooldown_ref_card_balance = account.cooldown_ref_card_balance
            existing.cooldown_ref_pot_balance = account.cooldown_ref_pot_balance
            existing.stable_pot_balance = account.stable_pot_balance
        else:
            # No record exists, add new.
            model = self._to_model(account)
            self._session.merge(model)
        self._session.commit()

    def delete(self, type: str) -> None:
        self._session.query(AccountModel).filter_by(type=type).delete()
        self._session.commit()

    def update_credit_account_fields(self, account_type: str, pot_id: str, 
                                     new_balance: int, cooldown_until: int = None) -> Account:
        record: AccountModel = self._session.query(AccountModel).filter_by(type=account_type).one()
        record.prev_balance = new_balance
        record.cooldown_until = cooldown_until
        self._session.commit()
        return self._to_domain(record)

    def get_by_id(self, account_id: str) -> Optional[MonzoAccount]:
        """Get an account by ID."""
        # Check Monzo accounts
        from app.models.monzo import MonzoAccount as DbMonzoAccount
        monzo_account = self._session.query(DbMonzoAccount).filter_by(id=account_id).first()
        if (monzo_account):
            return self._map_monzo_db_to_domain(monzo_account)
        
        # Check TrueLayer accounts if not found in Monzo
        # In a real implementation, you'd have a proper TrueLayer account model
        return None
    
    def get_by_user_id(self, user_id: str) -> List[MonzoAccount]:
        """Get all accounts for a user."""
        from app.models.monzo import MonzoAccount as DbMonzoAccount
        
        accounts = []
        
        # Get Monzo accounts
        monzo_accounts = self._session.query(DbMonzoAccount).filter_by(user_id=user_id).all()
        for account in monzo_accounts:
            accounts.append(self._map_monzo_db_to_domain(account))
        
        # Get TrueLayer accounts
        # In a real implementation, you'd add TrueLayer accounts here
        
        return accounts
    
    def save(self, account) -> None:
        """Save an account."""
        try:
            if isinstance(account, MonzoAccount):
                self._save_monzo_account(account)
            elif isinstance(account, TrueLayerAccount):
                self._save_truelayer_account(account)
            else:
                raise ValueError(f"Unsupported account type: {type(account)}")
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error saving account: {str(e)}")
            raise
    
    def _save_monzo_account(self, account: MonzoAccount) -> None:
        """Save a Monzo account."""
        from app.models.monzo import MonzoAccount as DbMonzoAccount
        
        db_account = self._session.query(DbMonzoAccount).filter_by(id=account.id).first()
        
        if db_account:
            # Update existing account
            db_account.name = account.name
            db_account.access_token = account.access_token
            db_account.refresh_token = account.refresh_token
            db_account.token_expires_at = datetime.fromtimestamp(account.token_expires_at)
            db_account.is_active = account.is_active
            db_account.sync_enabled = account.sync_enabled
            db_account.updated_at = datetime.utcnow()
        else:
            # Create new account
            db_account = DbMonzoAccount(
                id=account.id if account.id else str(uuid.uuid4()),
                user_id=account.user_id,
                name=account.name,
                type="monzo",
                access_token=account.access_token,
                refresh_token=account.refresh_token,
                token_expires_at=datetime.fromtimestamp(account.token_expires_at),
                is_active=account.is_active,
                sync_enabled=account.sync_enabled,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self._session.add(db_account)
        
        self._session.commit()
    
    def _save_truelayer_account(self, account: TrueLayerAccount) -> None:
        """Save a TrueLayer account."""
        # In a real implementation, you'd have a proper TrueLayer account model
        # For now, let's assume it's similar to Monzo
        pass
    
    def delete(self, account_id: str) -> bool:
        """Delete an account by ID."""
        try:
            # Try to delete from Monzo accounts
            from app.models.monzo import MonzoAccount as DbMonzoAccount
            monzo_account = self._session.query(DbMonzoAccount).filter_by(id=account_id).first()
            if monzo_account:
                self._session.delete(monzo_account)
                self._session.commit()
                return True
            
            # If not found in Monzo, try TrueLayer
            # In a real implementation, you'd try to delete from TrueLayer accounts
            
            return False
        except SQLAlchemyError as e:
            self._session.rollback()
            log.error(f"Error deleting account: {str(e)}")
            raise
    
    def _map_monzo_db_to_domain(self, db_account) -> MonzoAccount:
        """Map a database Monzo account to domain model."""
        return MonzoAccount(
            id=db_account.id,
            user_id=db_account.user_id,
            name=db_account.name,
            access_token=db_account.access_token,
            refresh_token=db_account.refresh_token,
            token_expires_at=int(db_account.token_expires_at.timestamp()),
            pot_id=db_account.pot_id,
            is_active=db_account.is_active,
            sync_enabled=db_account.sync_enabled
        )