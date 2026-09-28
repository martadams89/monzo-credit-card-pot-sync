import hashlib
import json
import logging
from time import time

from sqlalchemy.orm import Session

from app.models.setting import SettingModel
from app.models.sync_run import SyncRunModel

log = logging.getLogger("sync_log")

DEFAULT_RETENTION_DAYS = 7
LEVEL_ORDER = {"INFO": 0, "WARNING": 1, "ERROR": 2}


def _fingerprint(lines: list) -> str:
    content = "\n".join(f"{level}|{logger}|{message}" for _, level, logger, message in lines)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _max_level(lines: list) -> str:
    return max((level for _, level, _, _ in lines), key=lambda lvl: LEVEL_ORDER.get(lvl, 0), default="INFO")


class SqlAlchemySyncRunRepository:
    """Stores sync run logs, collapsing consecutive identical runs into one row.

    Uses its own session on the engine rather than ``db.session``: a sync run that
    fails can leave ``db.session`` mid-transaction, and saving its log must not
    depend on (or commit) whatever the sync left behind.
    """

    def __init__(self, db) -> None:
        self._db = db

    def _session(self) -> Session:
        return Session(self._db.engine)

    def retention_days(self, session: Session) -> int:
        setting = session.get(SettingModel, "log_retention_days")
        try:
            days = int(setting.value) if setting is not None else DEFAULT_RETENTION_DAYS
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        return max(days, 1)

    def record(self, lines: list, started_at: float, finished_at: float | None = None) -> SyncRunModel:
        finished_at = finished_at if finished_at is not None else time()
        fingerprint = _fingerprint(lines)
        with self._session() as session:
            latest = session.query(SyncRunModel).order_by(SyncRunModel.id.desc()).first()
            if latest is not None and latest.fingerprint == fingerprint:
                latest.repeat_count += 1
                latest.last_started_at = started_at
                latest.finished_at = finished_at
                run = latest
            else:
                run = SyncRunModel(
                    started_at=started_at,
                    last_started_at=started_at,
                    finished_at=finished_at,
                    repeat_count=1,
                    level=_max_level(lines),
                    fingerprint=fingerprint,
                    lines=json.dumps(lines),
                )
                session.add(run)

            cutoff = finished_at - self.retention_days(session) * 86400
            session.query(SyncRunModel).filter(SyncRunModel.finished_at < cutoff).delete()
            session.commit()
            session.refresh(run)
            session.expunge(run)
            return run

    def list_since(self, since: float, limit: int = 500) -> list[dict]:
        """Return distinct runs newest first, each with the lines that changed since the run before it."""
        with self._session() as session:
            rows = (
                session.query(SyncRunModel)
                .filter(SyncRunModel.finished_at >= since)
                .order_by(SyncRunModel.id.desc())
                .limit(limit + 1)
                .all()
            )
            # One run older than the window, so the oldest run shown can still be diffed.
            if len(rows) <= limit:
                oldest_id = rows[-1].id if rows else None
                older = (
                    session.query(SyncRunModel)
                    .filter(SyncRunModel.id < oldest_id)
                    .order_by(SyncRunModel.id.desc())
                    .first()
                    if oldest_id is not None
                    else None
                )
                baseline = older
            else:
                baseline = rows.pop()

            runs = []
            for row in rows:
                runs.append({
                    "id": row.id,
                    "started_at": row.started_at,
                    "last_started_at": row.last_started_at,
                    "finished_at": row.finished_at,
                    "repeat_count": row.repeat_count,
                    "level": row.level,
                    "lines": [
                        {"time": t, "level": level, "logger": logger, "message": message}
                        for t, level, logger, message in json.loads(row.lines)
                    ],
                })
            baseline_lines = (
                {(level, logger, message) for _, level, logger, message in json.loads(baseline.lines)}
                if baseline is not None
                else None
            )

        # Walk oldest to newest, flagging lines that the previous distinct run did not have.
        previous = baseline_lines
        for run in reversed(runs):
            keys = {(line["level"], line["logger"], line["message"]) for line in run["lines"]}
            changed = 0
            for line in run["lines"]:
                line["changed"] = previous is not None and (line["level"], line["logger"], line["message"]) not in previous
                changed += line["changed"]
            run["changed_count"] = changed
            run["removed_count"] = len(previous - keys) if previous is not None else 0
            run["is_first"] = previous is None
            previous = keys
        return runs
