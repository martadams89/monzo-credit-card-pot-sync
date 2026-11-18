from sqlalchemy import Column, Float, Integer, String

from app.extensions import db


class PotMovementModel(db.Model):
    """One deposit into or withdrawal from a pot made by the sync."""

    __tablename__ = "pot_movement"

    id = Column(Integer, primary_key=True)
    created_at = Column(Float, nullable=False, index=True)
    # The card connection the move was made for, e.g. "American Express".
    card = Column(String(255), nullable=False)
    pot_id = Column(String(255), nullable=False, index=True)
    # "deposit" or "withdrawal".
    direction = Column(String(10), nullable=False)
    # Pence, always positive; ``direction`` gives the sign.
    amount = Column(Integer, nullable=False)
    # Why the move was made: see ``app.models.pot_history_repository.REASONS``.
    reason = Column(String(32), nullable=False)
    pot_before = Column(Integer, nullable=True)
    pot_after = Column(Integer, nullable=True)
    card_balance = Column(Integer, nullable=True)


class PotBalanceSnapshotModel(db.Model):
    """A pot's balance, and what the cards synced with it owe, at the end of a sync.

    A row is only written when either figure changes (or every few hours as a
    heartbeat), so a quiet pot costs a handful of rows a day.
    """

    __tablename__ = "pot_balance_snapshot"

    id = Column(Integer, primary_key=True)
    recorded_at = Column(Float, nullable=False, index=True)
    pot_id = Column(String(255), nullable=False, index=True)
    pot_name = Column(String(255), nullable=True)
    pot_balance = Column(Integer, nullable=False)
    # Combined balance of every card synced with this pot; NULL if one couldn't be read.
    card_balance = Column(Integer, nullable=True)
