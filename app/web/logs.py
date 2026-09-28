import datetime
from time import time

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import security
from app.extensions import db
from app.models.sync_run_repository import SqlAlchemySyncRunRepository

logs_bp = Blueprint("logs", __name__)

repository = SqlAlchemySyncRunRepository(db)

PERIODS = {"1": "Last 24 hours", "3": "Last 3 days", "7": "Last 7 days", "30": "Last 30 days"}
DEFAULT_PERIOD = "3"
MAX_RUNS = 500


@logs_bp.route("/", methods=["GET"])
def index():
    if not security.log_history_enabled():
        return render_template("logs/disabled.html")
    period = request.args.get("days", DEFAULT_PERIOD)
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    runs = repository.list_since(time() - int(period) * 86400, limit=MAX_RUNS)
    return render_template(
        "logs/index.html",
        runs=runs,
        total_runs=sum(run["repeat_count"] for run in runs),
        periods=PERIODS,
        period=period,
        max_runs=MAX_RUNS,
    )


@logs_bp.route("/clear", methods=["POST"])
def clear():
    removed = repository.clear()
    flash(f"Log history cleared ({removed} entr{'y' if removed == 1 else 'ies'})")
    return redirect(url_for("logs.index"))


@logs_bp.app_template_filter("utc_datetime")
def utc_datetime(timestamp: float) -> str:
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@logs_bp.app_template_filter("utc_clock")
def utc_clock(timestamp: float) -> str:
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime("%H:%M:%S")
