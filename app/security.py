"""Optional login for the web UI: password, authenticator app (TOTP) 2FA and passkeys.

Login is off by default ("none"), for installs that sit behind a reverse proxy that
already handles authentication. In "password" mode every page except the login
pages, static files and /health needs a signed-in session. A passkey signs in on
its own; a password needs the authenticator code too when 2FA is on.

If you are locked out, start the app with POT_SYNC_DISABLE_AUTH=true, then change
the password, 2FA or passkeys under Settings > Security.
"""

import logging
import os
import secrets
import threading
from time import time
from urllib.parse import urlparse

import pyotp
from flask import current_app, jsonify, redirect, request, session, url_for
from sqlalchemy.exc import NoResultFound
from werkzeug.security import check_password_hash, generate_password_hash

from app.domain.settings import Setting
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository

log = logging.getLogger("security")

AUTH_MODE_NONE = "none"
AUTH_MODE_PASSWORD = "password"
MIN_PASSWORD_LENGTH = 8

# Endpoints reachable without signing in.
PUBLIC_ENDPOINTS = {
    "static",
    "health.health",
    "login.login",
    "login.two_factor",
    "login.passkey_options",
    "login.passkey_verify",
}

# Failed sign-in attempts per client before sign-in is paused for that client.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

settings = SqlAlchemySettingRepository(db)


def get_setting(key: str, default=None):
    try:
        value = settings.get(key)
    except NoResultFound:
        return default
    return default if value in (None, "") else value


def set_setting(key: str, value) -> None:
    settings.save(Setting(key, value))


def setting_on(key: str, default: bool) -> bool:
    """Read an on/off setting stored as True/False, "True"/"False" or "1"/"0"."""
    value = get_setting(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "on", "yes")


def log_history_enabled() -> bool:
    return setting_on("log_history_enabled", True)


def hide_balances() -> bool:
    return setting_on("hide_balances", False)


def auth_disabled_by_env() -> bool:
    return os.environ.get("POT_SYNC_DISABLE_AUTH", "").strip().lower() in ("1", "true", "yes", "on")


def auth_mode() -> str:
    return get_setting("auth_mode", AUTH_MODE_NONE)


def auth_required() -> bool:
    """Whether the web UI needs a signed-in session right now."""
    return (
        auth_mode() == AUTH_MODE_PASSWORD
        and get_setting("auth_password_hash") is not None
        and not auth_disabled_by_env()
    )


def totp_enabled() -> bool:
    return get_setting("auth_totp_secret") is not None


def check_password(password: str) -> bool:
    password_hash = get_setting("auth_password_hash")
    return bool(password_hash) and check_password_hash(password_hash, password or "")


def set_password(password: str) -> None:
    set_setting("auth_password_hash", generate_password_hash(password))
    bump_session_version()


def bump_session_version() -> None:
    """Sign out every existing session (after a password change or disabling login)."""
    set_setting("auth_session_version", secrets.token_hex(8))


def session_version() -> str:
    return get_setting("auth_session_version", "0")


def sign_in() -> None:
    """Start a fresh signed-in session (a new session guards against fixation)."""
    next_url = session.get("next")
    session.clear()
    session.permanent = True
    session["authenticated"] = True
    session["auth_version"] = session_version()
    if next_url:
        session["next"] = next_url


def is_signed_in() -> bool:
    return bool(session.get("authenticated")) and session.get("auth_version") == session_version()


# ---------------------------------------------------------------------------
# Sign-in throttling
# ---------------------------------------------------------------------------

_failures: dict[str, list[float]] = {}
_failures_lock = threading.Lock()


def _client_key() -> str:
    return request.remote_addr or "unknown"


def seconds_until_unlocked() -> int:
    now = time()
    with _failures_lock:
        attempts = [t for t in _failures.get(_client_key(), []) if now - t < LOCKOUT_SECONDS]
        _failures[_client_key()] = attempts
        if len(attempts) < MAX_FAILED_ATTEMPTS:
            return 0
        return int(LOCKOUT_SECONDS - (now - attempts[-MAX_FAILED_ATTEMPTS])) + 1


def record_failed_attempt() -> None:
    log.warning(f"Failed sign-in attempt from {_client_key()}")
    with _failures_lock:
        _failures.setdefault(_client_key(), []).append(time())


def clear_failed_attempts() -> None:
    with _failures_lock:
        _failures.pop(_client_key(), None)


def reset_throttle() -> None:
    with _failures_lock:
        _failures.clear()


# ---------------------------------------------------------------------------
# Authenticator app (TOTP)
# ---------------------------------------------------------------------------

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name="Pot Sync", issuer_name="Monzo Credit Card Pot Sync")


def verify_totp(secret: str, code: str) -> bool:
    """Check a 6-digit code, allowing one step of clock drift, and refuse a code
    that has already been used (so a code seen over someone's shoulder can't be
    replayed within its 30 seconds)."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6 or not secret:
        return False
    totp = pyotp.TOTP(secret)
    now = time()
    for offset in (-1, 0, 1):
        step_time = now + offset * totp.interval
        if secrets.compare_digest(totp.at(step_time), code):
            step = int(step_time // totp.interval)
            if step <= int(get_setting("auth_totp_last_step", -1)):
                return False
            set_setting("auth_totp_last_step", str(step))
            return True
    return False


# ---------------------------------------------------------------------------
# Passkeys (WebAuthn)
# ---------------------------------------------------------------------------

def _local_url() -> str:
    return current_app.config.get("LOCAL_URL") or "http://localhost:1337"


def webauthn_rp_id() -> str:
    """The domain passkeys are bound to: the host of POT_SYNC_LOCAL_URL (the public
    URL the app is reached on, also used for the OAuth callbacks)."""
    return urlparse(_local_url()).hostname or "localhost"


def webauthn_expected_origins() -> list[str]:
    """Origins a passkey ceremony may come from. The browser signs the origin and
    the authenticator signs the RP ID, so accepting the configured URL plus the host
    the request came in on (when it is that same domain) is safe."""
    configured = urlparse(_local_url())
    origins = {f"{configured.scheme}://{configured.netloc}"}
    rp_id = webauthn_rp_id()
    host = request.host
    hostname = host.split(":")[0]
    if hostname == rp_id or hostname.endswith("." + rp_id):
        origins.update({f"https://{host}", f"http://{host}"})
    return sorted(origins)


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

def persistent_secret_key() -> str:
    """A random session-signing key, generated once and kept in the database.

    Used when SECRET_KEY isn't set: the old fixed default would let anyone sign a
    session cookie and so walk past the login.
    """
    key = get_setting("secret_key")
    if key is None:
        key = secrets.token_hex(32)
        set_setting("secret_key", key)
    return key


def require_login():
    """before_request hook: send signed-out visitors to the login page."""
    if request.endpoint in PUBLIC_ENDPOINTS or not auth_required() or is_signed_in():
        return None
    if request.method == "GET" and not request.path.startswith("/login"):
        session["next"] = request.full_path if request.query_string else request.path
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return jsonify({"error": "Sign in required"}), 401
    return redirect(url_for("login.login"))


def inject_auth_context():
    return {
        "auth_enabled": auth_required(),
        "signed_in": auth_required() and is_signed_in(),
        "log_history_enabled": log_history_enabled(),
    }
