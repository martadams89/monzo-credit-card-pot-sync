import datetime
import logging
from time import time

from apscheduler.jobstores.base import JobLookupError
from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy.exc import NoResultFound

from app import security, sync_status
from app.extensions import db, scheduler
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.sync_run_repository import SqlAlchemySyncRunRepository

home_bp = Blueprint("home", __name__)

log = logging.getLogger("home")
account_repository = SqlAlchemyAccountRepository(db)
sync_runs = SqlAlchemySyncRunRepository(db)

# Warn about a connection this long before its consent expires.
RECONNECT_WARNING_DAYS = 14


def _setup_steps(monzo_connected: bool, credit_accounts: list) -> list[dict]:
    return [
        {
            "label": "Add your Monzo and TrueLayer client IDs and secrets",
            "done": bool(security.get_setting("monzo_client_id")) and bool(security.get_setting("truelayer_client_id")),
            "url": url_for("settings.index"),
        },
        {"label": "Connect your Monzo account", "done": monzo_connected, "url": url_for("accounts.add_account")},
        {"label": "Connect a credit card", "done": bool(credit_accounts), "url": url_for("accounts.add_account")},
        {
            "label": "Choose the pot each card syncs with",
            "done": bool(credit_accounts) and all(a.pot_id and a.pot_id != "default_pot" for a in credit_accounts),
            "url": url_for("pots.index"),
        },
    ]


@home_bp.route("/", methods=["GET"])
def index():
    try:
        account_repository.get_monzo_account()
        monzo_connected = True
    except NoResultFound:
        monzo_connected = False
    credit_accounts = account_repository.get_credit_accounts()
    steps = _setup_steps(monzo_connected, credit_accounts)

    status = sync_status.load()
    snapshot = {a["type"]: a for a in status["accounts"]}
    now = int(time())
    # Cards that share a pot are funded from it together, so the pot is compared with
    # their combined balance.
    by_pot: dict[str, list] = {}
    for account in credit_accounts:
        by_pot.setdefault(account.pot_id, []).append(account)
    cards = []
    for account in credit_accounts:
        seen = snapshot.get(account.type, {})
        card_balance = seen.get("card_balance")
        pot_balance = seen.get("pot_balance") if seen.get("pot_id") == account.pot_id else None
        sharing = [other for other in by_pot.get(account.pot_id, []) if other.type != account.type]
        owed = [snapshot.get(a.type, {}).get("card_balance") for a in by_pot.get(account.pot_id, [account])]
        total_owed = None if any(o is None for o in owed) else sum(owed)
        expires = account.consent_expires_at
        cards.append({
            "type": account.type,
            "icon": account.auth_provider.icon_name,
            "card_balance": card_balance,
            "pot_name": seen.get("pot_name") if seen.get("pot_id") == account.pot_id else None,
            "pot_balance": pot_balance,
            "difference": (pot_balance - total_owed) if total_owed is not None and pot_balance is not None else None,
            "shared_with": [other.type for other in sharing],
            "cooldown_until": account.cooldown_until if account.cooldown_until and account.cooldown_until > now else None,
            "consent_expires_at": expires,
            "reconnect_soon": expires is not None and expires - now < RECONNECT_WARNING_DAYS * 86400,
        })

    return render_template(
        "index.html",
        setup_complete=all(step["done"] for step in steps),
        steps=steps,
        cards=cards,
        latest=sync_runs.latest(),
        checked_at=status["checked_at"],
        sync_enabled=str(security.get_setting("enable_sync", True)).lower() in ("true", "1"),
        now=now,
    )


@home_bp.route("/sync-now", methods=["POST"])
def sync_now():
    """Run the sync straight away instead of waiting for the next interval."""
    try:
        scheduler.modify_job("sync_balance", next_run_time=datetime.datetime.now(datetime.timezone.utc))
        flash("Sync started. Refresh in a few seconds to see the result.")
    except (JobLookupError, AttributeError, RuntimeError) as e:
        log.error(f"Could not start a sync: {e}")
        flash("Couldn't start a sync right now", "error")
    return redirect(url_for("home.index"))


@home_bp.app_template_filter("pounds")
def pounds(pence) -> str:
    if pence is None:
        return "–"
    sign = "-" if pence < 0 else ""
    return f"{sign}£{abs(pence) / 100:,.2f}"


@home_bp.app_template_filter("relative_time")
def relative_time(timestamp) -> str:
    """A short "5 minutes ago" / "in 2 hours" description of an epoch time."""
    if not timestamp:
        return "never"
    delta = int(timestamp - time())
    future = delta > 0
    seconds = abs(delta)
    if seconds < 60:
        text = "a few seconds" if seconds > 5 else "just now"
        if text == "just now":
            return text
    elif seconds < 3600:
        text = f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        text = f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = seconds // 86400
        text = f"{days} day{'s' if days != 1 else ''}"
    return f"in {text}" if future else f"{text} ago"
