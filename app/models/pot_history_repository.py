"""History of the money the sync moves, and of each pot's balance over time.

Like the sync log, this uses its own session on the engine rather than
``db.session``: a sync run that fails can leave ``db.session`` mid-transaction,
and recording history must not depend on (or commit) whatever it left behind.
Every write swallows and logs its own errors so history can never fail a sync.
"""

import logging
from time import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.pot_history import PotBalanceSnapshotModel, PotMovementModel

log = logging.getLogger("pot_history")

REASONS = {
    "spending": "Card spending",
    "over_funded": "Pot over card balance",
    "cooldown_expired": "Cooldown ended",
    "override_spending": "Spending during cooldown",
}

# Write a snapshot at least this often even when nothing changed, so the chart
# shows the pot was still being watched.
SNAPSHOT_HEARTBEAT_SECONDS = 6 * 3600
# Balance snapshots are pruned after this long; moves are kept until cleared.
SNAPSHOT_RETENTION_DAYS = 400


class SqlAlchemyPotHistoryRepository:
    def __init__(self, db) -> None:
        self._db = db

    def _session(self) -> Session:
        return Session(self._db.engine)

    # ------------------------------------------------------------------ moves

    def record_move(
        self,
        card: str,
        pot_id: str,
        direction: str,
        amount: int,
        reason: str,
        pot_before: int | None = None,
        pot_after: int | None = None,
        card_balance: int | None = None,
        created_at: float | None = None,
    ) -> None:
        try:
            with self._session() as session:
                session.add(PotMovementModel(
                    created_at=created_at if created_at is not None else time(),
                    card=card,
                    pot_id=pot_id,
                    direction=direction,
                    amount=int(amount),
                    reason=reason,
                    pot_before=pot_before,
                    pot_after=pot_after,
                    card_balance=card_balance,
                ))
                session.commit()
        except Exception:  # history must never fail the sync
            log.exception("Failed to record a pot movement")

    def moves(self, since: float | None = None, limit: int = 500) -> list[dict]:
        """Moves newest first."""
        with self._session() as session:
            query = session.query(PotMovementModel)
            if since is not None:
                query = query.filter(PotMovementModel.created_at >= since)
            rows = query.order_by(PotMovementModel.created_at.desc(), PotMovementModel.id.desc()).limit(limit).all()
            return [
                {
                    "id": row.id,
                    "created_at": row.created_at,
                    "card": row.card,
                    "pot_id": row.pot_id,
                    "direction": row.direction,
                    "amount": row.amount,
                    "signed_amount": row.amount if row.direction == "deposit" else -row.amount,
                    "reason": row.reason,
                    "reason_label": REASONS.get(row.reason, row.reason),
                    "pot_before": row.pot_before,
                    "pot_after": row.pot_after,
                    "card_balance": row.card_balance,
                }
                for row in rows
            ]

    def totals(self, since: float | None = None) -> dict:
        """Total deposited and withdrawn, and how many moves, since a time."""
        with self._session() as session:
            query = session.query(
                PotMovementModel.direction, func.count(PotMovementModel.id), func.sum(PotMovementModel.amount)
            )
            if since is not None:
                query = query.filter(PotMovementModel.created_at >= since)
            result = {"deposited": 0, "withdrawn": 0, "count": 0}
            for direction, count, total in query.group_by(PotMovementModel.direction).all():
                result["count"] += count
                result["deposited" if direction == "deposit" else "withdrawn"] += total or 0
            return result

    # -------------------------------------------------------------- snapshots

    def record_snapshot(
        self,
        pot_id: str,
        pot_name: str | None,
        pot_balance: int,
        card_balance: int | None,
        recorded_at: float | None = None,
    ) -> bool:
        """Store a pot's balance unless it matches the latest one and that is recent.

        Returns whether a row was written.
        """
        recorded_at = recorded_at if recorded_at is not None else time()
        try:
            with self._session() as session:
                latest = (
                    session.query(PotBalanceSnapshotModel)
                    .filter(PotBalanceSnapshotModel.pot_id == pot_id)
                    .order_by(PotBalanceSnapshotModel.recorded_at.desc(), PotBalanceSnapshotModel.id.desc())
                    .first()
                )
                unchanged = (
                    latest is not None
                    and latest.pot_balance == pot_balance
                    and latest.card_balance == card_balance
                    and recorded_at - latest.recorded_at < SNAPSHOT_HEARTBEAT_SECONDS
                )
                if unchanged:
                    if pot_name and latest.pot_name != pot_name:
                        latest.pot_name = pot_name
                        session.commit()
                    return False
                session.add(PotBalanceSnapshotModel(
                    recorded_at=recorded_at,
                    pot_id=pot_id,
                    pot_name=pot_name,
                    pot_balance=pot_balance,
                    card_balance=card_balance,
                ))
                cutoff = recorded_at - SNAPSHOT_RETENTION_DAYS * 86400
                session.query(PotBalanceSnapshotModel).filter(PotBalanceSnapshotModel.recorded_at < cutoff).delete()
                session.commit()
                return True
        except Exception:  # history must never fail the sync
            log.exception("Failed to record a pot balance snapshot")
            return False

    def balance_series(self, since: float) -> list[dict]:
        """Each pot's balance over time, oldest point first.

        The last point before ``since`` is carried to the start of the window so
        the line starts at the left edge rather than at the first change inside it.
        """
        with self._session() as session:
            rows = (
                session.query(PotBalanceSnapshotModel)
                .filter(PotBalanceSnapshotModel.recorded_at >= since)
                .order_by(PotBalanceSnapshotModel.recorded_at, PotBalanceSnapshotModel.id)
                .all()
            )
            series: dict[str, dict] = {}
            for row in rows:
                pot = series.setdefault(row.pot_id, {"pot_id": row.pot_id, "pot_name": row.pot_name, "points": []})
                if row.pot_name:
                    pot["pot_name"] = row.pot_name
                pot["points"].append({"t": row.recorded_at, "pot": row.pot_balance, "card": row.card_balance})

            pot_ids = {
                pot_id
                for (pot_id,) in session.query(PotBalanceSnapshotModel.pot_id)
                .filter(PotBalanceSnapshotModel.recorded_at < since)
                .distinct()
                .all()
            }
            for pot_id in pot_ids:
                before = (
                    session.query(PotBalanceSnapshotModel)
                    .filter(PotBalanceSnapshotModel.pot_id == pot_id, PotBalanceSnapshotModel.recorded_at < since)
                    .order_by(PotBalanceSnapshotModel.recorded_at.desc(), PotBalanceSnapshotModel.id.desc())
                    .first()
                )
                pot = series.setdefault(pot_id, {"pot_id": pot_id, "pot_name": before.pot_name, "points": []})
                pot["pot_name"] = pot["pot_name"] or before.pot_name
                pot["points"].insert(0, {"t": since, "pot": before.pot_balance, "card": before.card_balance})

        return sorted(series.values(), key=lambda pot: (pot["pot_name"] or "", pot["pot_id"]))

    def pot_names(self) -> dict[str, str]:
        """The latest known name of every pot that has a snapshot."""
        with self._session() as session:
            rows = (
                session.query(PotBalanceSnapshotModel.pot_id, PotBalanceSnapshotModel.pot_name)
                .filter(PotBalanceSnapshotModel.pot_name.isnot(None))
                .order_by(PotBalanceSnapshotModel.recorded_at)
                .all()
            )
            return {pot_id: name for pot_id, name in rows}

    # ------------------------------------------------------------------ admin

    def clear(self) -> int:
        """Delete all moves and balance snapshots; returns how many rows were removed."""
        with self._session() as session:
            removed = session.query(PotMovementModel).delete() + session.query(PotBalanceSnapshotModel).delete()
            session.commit()
            return removed
