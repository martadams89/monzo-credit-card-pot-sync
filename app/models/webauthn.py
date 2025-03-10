from app.extensions import db
from datetime import datetime

class WebAuthnCredential(db.Model):
    """Model for WebAuthn credentials (passkeys)."""
    
    __tablename__ = "webauthn_credentials"
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    credential_id = db.Column(db.String(255), nullable=False, unique=True)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('webauthn_credentials', lazy=True))
    
    def __repr__(self):
        return f'<WebAuthnCredential {self.id}: {self.name}>'
