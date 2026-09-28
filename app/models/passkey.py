from sqlalchemy import Column, Integer, LargeBinary, String

from app.extensions import db


class PasskeyModel(db.Model):
    """A passkey (WebAuthn credential) that can sign in to the web UI."""

    __tablename__ = "passkey"

    id = Column(Integer, primary_key=True)
    # base64url credential id, as sent by the browser.
    credential_id = Column(String(1024), nullable=False, unique=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    name = Column(String(100), nullable=False)
    created_at = Column(Integer, nullable=False)
    last_used_at = Column(Integer, nullable=True)
