"""A snapshot of each card after the latest sync, shown on the home page.

Kept in the settings table as JSON so the dashboard never has to call the card or
Monzo APIs itself.
"""

import json
import logging

from app import security

log = logging.getLogger("sync_status")

KEY = "last_account_status"
LAST_RUN_KEY = "last_sync_run"
LEVEL_ORDER = {"INFO": 0, "WARNING": 1, "ERROR": 2}


def save(accounts: list[dict], checked_at: float) -> None:
    try:
        security.set_setting(KEY, json.dumps({"checked_at": checked_at, "accounts": accounts}))
    except Exception:
        log.exception("Failed to save the dashboard status")


def load() -> dict:
    raw = security.get_setting(KEY)
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}
    return {"checked_at": data.get("checked_at"), "accounts": data.get("accounts", [])}


def save_last_run(lines: list, started_at: float, finished_at: float) -> None:
    """Record when the latest sync ran, its highest level and its first problem.

    Kept separately from the log history so the dashboard and /health still work
    when log history is switched off.
    """
    level = max((lvl for _, lvl, _, _ in lines), key=lambda lvl: LEVEL_ORDER.get(lvl, 0), default="INFO")
    problem = next((msg for _, lvl, _, msg in reversed(lines) if lvl == level and level != "INFO"), None)
    try:
        security.set_setting(LAST_RUN_KEY, json.dumps({
            "last_started_at": started_at,
            "finished_at": finished_at,
            "level": level,
            "problem": problem.splitlines()[0] if problem else None,
        }))
    except Exception:
        log.exception("Failed to save the last sync run")


def last_run() -> dict | None:
    raw = security.get_setting(LAST_RUN_KEY)
    try:
        data = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        data = None
    return data if isinstance(data, dict) and data.get("finished_at") else None
