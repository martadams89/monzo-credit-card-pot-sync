import logging
import threading
from contextlib import contextmanager
from time import time

from app.extensions import db
from app.models.sync_run_repository import SqlAlchemySyncRunRepository

log = logging.getLogger("sync_log")

# Guards against a run that logs in a loop filling the database.
MAX_LINES_PER_RUN = 1000


class _RunCaptureHandler(logging.Handler):
    """Collects the log records emitted by one thread while a sync run is in progress."""

    def __init__(self, thread_id: int) -> None:
        super().__init__(level=logging.INFO)
        self._thread_id = thread_id
        self.lines: list = []
        self.truncated = 0

    def emit(self, record: logging.LogRecord) -> None:
        # Web requests log from other threads at the same time; keep only this run's.
        if record.thread != self._thread_id:
            return
        if len(self.lines) >= MAX_LINES_PER_RUN:
            self.truncated += 1
            return
        try:
            message = record.getMessage()
            if record.exc_info:
                message = f"{message}\n{logging.Formatter().formatException(record.exc_info)}"
            level = "ERROR" if record.levelno >= logging.ERROR else "WARNING" if record.levelno >= logging.WARNING else "INFO"
            self.lines.append([record.created, level, record.name, message])
        except Exception:
            self.handleError(record)


@contextmanager
def record_sync_run(repository: SqlAlchemySyncRunRepository | None = None):
    """Capture everything logged during a sync run and save it to the sync log history.

    Saving the log never interferes with the sync itself: a failure to save is
    logged and swallowed, and an exception raised by the sync is recorded then
    re-raised unchanged.
    """
    repository = repository or SqlAlchemySyncRunRepository(db)
    handler = _RunCaptureHandler(threading.get_ident())
    root = logging.getLogger()
    root.addHandler(handler)
    started_at = time()
    try:
        yield handler
    except Exception:
        log.exception("Sync run failed")
        raise
    finally:
        root.removeHandler(handler)
        lines = handler.lines
        if handler.truncated:
            lines.append([time(), "WARNING", "sync_log", f"{handler.truncated} further log line(s) not recorded"])
        try:
            repository.record(lines, started_at)
        except Exception as e:
            log.error(f"Failed to save sync log history: {e}")
