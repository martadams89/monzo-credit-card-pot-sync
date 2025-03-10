import uuid
from datetime import datetime
from app.extensions import db

class MonzoAccount(db.Model):
    """Model for storing Monzo account information."""
    
    __tablename__ = "monzo_accounts"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), default="monzo")
    account_id = db.Column(db.String(100), nullable=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=False)
    token_expires_at = db.Column(db.DateTime, nullable=False)
    balance = db.Column(db.Integer, default=0)  # Balance in pence
    currency = db.Column(db.String(3), default="GBP")
    is_active = db.Column(db.Boolean, default=True)
    sync_enabled = db.Column(db.Boolean, default=True)
    last_refreshed = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('monzo_accounts', lazy=True))
    pots = db.relationship('MonzoPot', backref='account', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<MonzoAccount {self.id}: {self.name}>'

class MonzoPot(db.Model):
    """Model for storing Monzo pot information."""
    
    __tablename__ = "monzo_pots"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('monzo_accounts.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    pot_id = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Integer, default=0)  # Balance in pence
    currency = db.Column(db.String(3), default="GBP")
    is_locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MonzoPot {self.id}: {self.name}>'

class MonzoTransaction(db.Model):
    """Model for Monzo transactions."""
    
    __tablename__ = "monzo_transactions"
    
    id = db.Column(db.String(36), primary_key=True)
    account_id = db.Column(db.String(36), db.ForeignKey('monzo_accounts.id'), nullable=False)
    transaction_id = db.Column(db.String(255), nullable=False, unique=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default='GBP')
    description = db.Column(db.String(255), nullable=True)
    merchant_name = db.Column(db.String(255), nullable=True)
    merchant_category = db.Column(db.String(255), nullable=True)
    settled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    account = db.relationship('MonzoAccount', backref=db.backref('transactions', lazy=True))
    
    def __repr__(self):
        return f'<MonzoTransaction {self.id}>'

class SyncRule(db.Model):
    """Model for storing sync rules."""
    
    __tablename__ = "sync_rules"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    source_account_id = db.Column(db.String(36), db.ForeignKey('monzo_accounts.id'), nullable=False)
    target_pot_id = db.Column(db.String(36), db.ForeignKey('monzo_pots.id'), nullable=False)
    trigger_type = db.Column(db.String(50), nullable=False)  # 'manual', 'daily', 'balance_change'
    action_type = db.Column(db.String(50), nullable=False)  # 'transfer_full_balance', 'transfer_amount', 'transfer_percentage'
    action_amount = db.Column(db.Integer, nullable=True)  # Amount in pence (for transfer_amount)
    action_percentage = db.Column(db.Integer, nullable=True)  # Percentage (for transfer_percentage)
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('sync_rules', lazy=True))
    source_account = db.relationship('MonzoAccount', foreign_keys=[source_account_id])
    target_pot = db.relationship('MonzoPot', foreign_keys=[target_pot_id])
    
    def __repr__(self):
        return f'<SyncRule {self.id}: {self.name}>'

class SyncHistory(db.Model):
    """Model for tracking sync operations history."""
    
    __tablename__ = "sync_history"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    rule_id = db.Column(db.String(36), db.ForeignKey('sync_rules.id'), nullable=True)
    amount = db.Column(db.Integer, default=0)  # Amount in pence
    status = db.Column(db.String(20), nullable=False)  # 'success', 'error', 'skipped'
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('sync_history', lazy=True))
    rule = db.relationship('SyncRule', backref=db.backref('history', lazy=True))
    
    def __repr__(self):
        return f'<SyncHistory {self.id}: {self.status}>'
