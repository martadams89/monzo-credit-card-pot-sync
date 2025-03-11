from app.extensions import db
from datetime import datetime

class WebAuthnCredential(db.Model):
    """Model for storing WebAuthn (passkey) credentials."""
    
    __tablename__ = "webauthn_credentials"
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    credential_id = db.Column(db.String(255), unique=True, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('webauthn_credentials', lazy=True))
    
    def __repr__(self):
        return f'<WebAuthnCredential {self.id}: {self.name}>'
