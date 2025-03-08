import datetime
from app.extensions import db
import json

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

class SyncHistory(db.Model):
    __tablename__ = 'sync_history'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)
    data = db.Column(db.Text, nullable=True)
    
    def __init__(self, status, data=None):
        self.status = status
        self.data = json.dumps(data, cls=DateTimeEncoder) if data else None
        
    @property
    def data_json(self):
        """Return data as Python dictionary"""
        if self.data:
            return json.loads(self.data)
        return {}
