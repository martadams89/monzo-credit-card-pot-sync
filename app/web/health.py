from time import time

from flask import Blueprint, jsonify

from app import security, sync_status
from app.extensions import db
from app.models.sync_run_repository import SqlAlchemySyncRunRepository

health_bp = Blueprint("health", __name__)

repository = SqlAlchemySyncRunRepository(db)


@health_bp.route("/health", methods=["GET"])
def health():
    """Whether the sync loop is alive, for Docker or an uptime monitor.

    Healthy (200) while a sync has finished within three sync intervals (at least
    five minutes). A run that logged an error is still reported as healthy, since
    the loop itself is running; its level is in the body for monitors that care.
    """
    try:
        interval = int(security.get_setting("sync_interval_seconds", 120))
    except (TypeError, ValueError):
        interval = 120
    max_age = max(3 * interval, 300)
    latest = sync_status.last_run() or repository.latest()
    if latest is None:
        return jsonify({"status": "starting", "detail": "No sync has run yet"}), 503

    age = int(time() - latest["finished_at"])
    body = {"last_sync_seconds_ago": age, "last_sync_level": latest["level"]}
    if age > max_age:
        return jsonify({"status": "stale", **body}), 503
    return jsonify({"status": "ok", **body}), 200
