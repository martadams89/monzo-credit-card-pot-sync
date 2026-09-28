"""A snapshot of each card after the latest sync, shown on the home page.

Kept in the settings table as JSON so the dashboard never has to call the card or
Monzo APIs itself.
"""

import json
import logging

from app import security

log = logging.getLogger("sync_status")

KEY = "last_account_status"


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
