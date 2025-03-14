import uuid
from datetime import datetime
from app.extensions import db

class SyncHistory(db.Model):
    """Model for tracking sync operations history."""
    
    __tablename__ = "sync_history"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user_account.id')), nullable=False)
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
    
    @staticmethod
    def get_stats_for_user(user_id, days=30):
        """Get sync statistics for a user over the specified number of days."""
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        # Calculate the start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get total syncs, successful syncs, and total amount
        total_syncs = db.session.query(func.count(SyncHistory.id)) \
            .filter(SyncHistory.user_id == user_id) \
            .filter(SyncHistory.created_at >= start_date) \
            .scalar() or 0
        
        successful_syncs = db.session.query(func.count(SyncHistory.id)) \
            .filter(SyncHistory.user_id == user_id) \
            .filter(SyncHistory.status == 'success') \
            .filter(SyncHistory.created_at >= start_date) \
            .scalar() or 0
        
        total_amount = db.session.query(func.sum(SyncHistory.amount)) \
            .filter(SyncHistory.user_id == user_id) \
            .filter(SyncHistory.status == 'success') \
            .filter(SyncHistory.created_at >= start_date) \
            .scalar() or 0
        
        return {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'total_amount': total_amount
        }
