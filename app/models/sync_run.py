from sqlalchemy import Column, Float, Integer, String, Text

from app.extensions import db


class SyncRunModel(db.Model):
    """The log output of one sync run, or of a streak of identical consecutive runs.

    Most runs log exactly the same lines as the run before (nothing changed), so
    rather than storing every run, a run whose lines match the latest stored run
    only bumps ``repeat_count`` and ``last_started_at`` on that row.
    """

    __tablename__ = "sync_run"

    id = Column(Integer, primary_key=True)
    # When the first run of the streak started, and when the latest one started/finished.
    started_at = Column(Float, nullable=False, index=True)
    last_started_at = Column(Float, nullable=False)
    finished_at = Column(Float, nullable=False, index=True)
    repeat_count = Column(Integer, nullable=False, default=1)
    # Highest level logged in the run: INFO, WARNING or ERROR.
    level = Column(String(10), nullable=False, default="INFO")
    # Hash of the run's (level, logger, message) lines, ignoring timestamps.
    fingerprint = Column(String(64), nullable=False)
    # JSON list of [timestamp, level, logger, message] from the first run of the streak.
    lines = Column(Text, nullable=False, default="[]")
