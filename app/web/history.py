from time import time

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import security, sync_status
from app.extensions import db
from app.models.pot_history_repository import SqlAlchemyPotHistoryRepository

history_bp = Blueprint("history", __name__)

repository = SqlAlchemyPotHistoryRepository(db)

PERIODS = {"7": "Last 7 days", "30": "Last 30 days", "90": "Last 90 days", "365": "Last year"}
DEFAULT_PERIOD = "30"
MAX_MOVES = 1000


def pot_names() -> dict[str, str]:
    """Pot names from the balance history, overridden by the latest dashboard snapshot."""
    names = repository.pot_names()
    for account in sync_status.load()["accounts"]:
        if account.get("pot_id") and account.get("pot_name"):
            names[account["pot_id"]] = account["pot_name"]
    return names


def chart_data(since: float, now: float, names: dict[str, str]) -> dict:
    """Everything the balance chart script needs, as plain JSON-able data."""
    series = repository.balance_series(since)
    for pot in series:
        pot["pot_name"] = names.get(pot["pot_id"]) or pot["pot_name"] or "Pot"
    moves = [
        {
            "t": move["created_at"],
            "pot_id": move["pot_id"],
            "card": move["card"],
            "amount": move["signed_amount"],
            "pot_after": move["pot_after"],
            "reason": move["reason_label"],
        }
        for move in repository.moves(since=since, limit=MAX_MOVES)
    ]
    return {"since": since, "now": now, "pots": series, "moves": moves}


@history_bp.route("/", methods=["GET"])
def index():
    period = request.args.get("days", DEFAULT_PERIOD)
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    now = time()
    since = now - int(period) * 86400
    names = pot_names()
    moves = repository.moves(since=since, limit=MAX_MOVES)
    for move in moves:
        move["pot_name"] = names.get(move["pot_id"], "Pot")
    return render_template(
        "history/index.html",
        moves=moves,
        totals=repository.totals(since=since),
        chart=chart_data(since, now, names),
        periods=PERIODS,
        period=period,
        max_moves=MAX_MOVES,
        hide_balances=security.hide_balances(),
    )


@history_bp.route("/clear", methods=["POST"])
def clear():
    removed = repository.clear()
    flash(f"History cleared ({removed} entr{'y' if removed == 1 else 'ies'})")
    return redirect(url_for("history.index"))
