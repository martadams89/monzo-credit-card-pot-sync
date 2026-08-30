from sqlalchemy import Column, Integer, String

from app.extensions import db


class AccountModel(db.Model):
    id = Column(Integer, primary_key=True)
    # ``type`` is the user-facing connection name (for example, "American
    # Express 2"). ``provider`` retains the underlying provider so multiple
    # independently-authorised connections can use the same integration.
    type = Column(String(50), nullable=False, unique=True)
    provider = Column(String(50), nullable=True)
    access_token = Column(String(255), nullable=False)
    refresh_token = Column(String(255), nullable=False)
    token_expiry = Column(Integer)
    pot_id = Column(String(255))
    account_id = Column(String(255))
    cooldown_until = Column(Integer, nullable=True)
    prev_balance = Column(Integer, default=0)
    cooldown_ref_card_balance = Column(Integer, default=0)
    cooldown_ref_pot_balance = Column(Integer, default=0)
    stable_pot_balance = Column(Integer, nullable=True)
