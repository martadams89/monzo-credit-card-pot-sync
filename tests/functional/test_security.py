"""Tests for the optional web UI sign in: password, 2FA (TOTP), session handling,
the login guard, throttling and the session signing key."""

from urllib.parse import urlparse

import pyotp
import pytest

from app import create_app, security
from app.extensions import db
from app.models.passkey import PasskeyModel

PASSWORD = "correct horse battery"
TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
# Middle of a 30 second TOTP step, so +/- one step is unambiguous.
FIXED_NOW = 1_700_000_025.0


@pytest.fixture(autouse=True)
def _reset_throttle(monkeypatch):
    monkeypatch.delenv("POT_SYNC_DISABLE_AUTH", raising=False)
    security.reset_throttle()
    yield
    security.reset_throttle()


@pytest.fixture
def client(test_client):
    test_client.application.config["LOCAL_URL"] = "https://pots.example.com"
    return test_client


def enable_login(password=PASSWORD, totp_secret=None):
    security.set_password(password)
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    if totp_secret:
        security.set_setting("auth_totp_secret", totp_secret)


def sign_in(client, password=PASSWORD):
    return client.post("/login", data={"password": password})


def path(response):
    return urlparse(response.location).path


def full_target(response):
    parsed = urlparse(response.location)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def freeze_time(monkeypatch, now):
    monkeypatch.setattr("app.security.time", lambda: now)
    monkeypatch.setattr("app.web.login.time", lambda: now)


# ---------------------------------------------------------------------------
# Defaults and the guard
# ---------------------------------------------------------------------------

def test_auth_off_by_default_pages_are_open(client):
    assert security.auth_mode() == security.AUTH_MODE_NONE
    assert security.auth_required() is False
    response = client.get("/settings/security/")
    assert response.status_code == 200
    assert b"Set a password" in response.data
    # The login page just sends you home when sign in is off.
    response = client.get("/login")
    assert response.status_code == 302
    assert path(response) == "/"


def test_password_mode_without_password_is_not_enforced(client):
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    assert security.auth_required() is False
    assert client.get("/settings/security/").status_code == 200


def test_guard_redirects_signed_out_get_and_returns_to_it(client):
    enable_login()
    response = client.get("/settings/security/?tab=passkeys")
    assert response.status_code == 302
    assert path(response) == "/login"

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert b"Sign in" in login_page.data
    assert b"Sign in with a passkey" not in login_page.data

    response = sign_in(client)
    assert response.status_code == 302
    assert full_target(response) == "/settings/security/?tab=passkeys"
    assert client.get("/settings/security/").status_code == 200


def test_guard_remembers_path_without_query_string(client):
    enable_login()
    client.get("/settings/")
    with client.session_transaction() as sess:
        assert sess["next"] == "/settings/"


def test_guard_does_not_remember_post_or_login_paths(client):
    enable_login()
    response = client.post("/settings/", data={"monzo_client_id": "x"})
    assert response.status_code == 302
    assert path(response) == "/login"
    response = client.get("/login/unknown")
    assert response.status_code == 302
    assert path(response) == "/login"
    with client.session_transaction() as sess:
        assert "next" not in sess
    # The blocked POST didn't change anything.
    assert security.get_setting("monzo_client_id") is None

    response = sign_in(client)
    assert path(response) == "/"


@pytest.mark.parametrize("target", ["//evil.example.com/", "https://evil.example.com/", "/\\evil.example.com", "evil"])
def test_next_only_allows_local_paths(client, target):
    enable_login()
    with client.session_transaction() as sess:
        sess["next"] = target
    response = sign_in(client)
    assert response.status_code == 302
    assert response.location == "/"


def test_json_requests_get_401(client):
    enable_login()
    response = client.get("/settings/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Sign in required"}

    response = client.post("/settings/security/passkeys/options", json={})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Sign in required"}


def test_public_endpoints_stay_open(client):
    enable_login()
    health = client.get("/health")
    assert health.status_code == 503
    assert health.get_json()["status"] == "starting"
    static = client.get("/static/js/passkeys.js")
    assert static.status_code == 200
    static.close()
    assert client.get("/login").status_code == 200
    # Without a password step, the 2FA page sends you back to the password.
    assert path(client.get("/login/2fa")) == "/login"
    assert client.post("/login/passkey/options").status_code == 200
    # Reaches the passkey lookup rather than the "Sign in required" guard.
    response = client.post("/login/passkey/verify", json={})
    assert response.status_code == 401
    assert response.get_json() == {"error": "This passkey isn't registered here"}


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
def test_env_escape_hatch_disables_auth(client, monkeypatch, value):
    enable_login()
    monkeypatch.setenv("POT_SYNC_DISABLE_AUTH", value)
    assert security.auth_disabled_by_env() is True
    assert security.auth_required() is False
    response = client.get("/settings/security/")
    assert response.status_code == 200
    assert b"POT_SYNC_DISABLE_AUTH" in response.data


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_env_escape_hatch_other_values_keep_auth(client, monkeypatch, value):
    enable_login()
    monkeypatch.setenv("POT_SYNC_DISABLE_AUTH", value)
    assert security.auth_disabled_by_env() is False
    assert client.get("/settings/security/").status_code == 302


# ---------------------------------------------------------------------------
# Password login and throttling
# ---------------------------------------------------------------------------

def test_login_page_redirects_when_already_signed_in(client):
    enable_login()
    sign_in(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert path(response) == "/"


def test_login_page_offers_passkey_when_one_is_registered(client):
    enable_login()
    db.session.add(PasskeyModel(credential_id="abc", public_key=b"k", sign_count=0, name="Phone", created_at=1))
    db.session.commit()
    assert b"Sign in with a passkey" in client.get("/login").data


def test_wrong_password_is_rejected(client):
    enable_login()
    response = sign_in(client, "wrong password")
    assert response.status_code == 401
    assert b"Incorrect password" in response.data
    assert client.get("/settings/security/").status_code == 302
    response = client.post("/login", data={})
    assert response.status_code == 401


def test_check_password_without_hash_is_false(client):
    assert security.check_password("anything") is False
    assert security.check_password(None) is False


def test_throttle_locks_after_five_failures(client, monkeypatch):
    enable_login()
    monkeypatch.setattr("app.security.time", lambda: FIXED_NOW)
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        assert sign_in(client, "nope").status_code == 401

    # Even the right password is refused while locked.
    response = sign_in(client)
    assert response.status_code == 429
    assert b"Too many failed attempts. Try again in 15 minute(s)." in response.data
    assert client.get("/settings/security/").status_code == 302

    # Another client address is not affected.
    other = client.application.test_client()
    response = other.post("/login", data={"password": PASSWORD}, environ_base={"REMOTE_ADDR": "10.0.0.9"})
    assert response.status_code == 302

    # After the lockout window the attempts expire.
    monkeypatch.setattr("app.security.time", lambda: FIXED_NOW + security.LOCKOUT_SECONDS)
    assert sign_in(client).status_code == 302


def test_seconds_until_unlocked_counts_down(client, monkeypatch):
    with client.application.test_request_context("/login"):
        monkeypatch.setattr("app.security.time", lambda: FIXED_NOW)
        assert security.seconds_until_unlocked() == 0
        for _ in range(security.MAX_FAILED_ATTEMPTS):
            security.record_failed_attempt()
        assert security.seconds_until_unlocked() == security.LOCKOUT_SECONDS + 1
        monkeypatch.setattr("app.security.time", lambda: FIXED_NOW + 600)
        assert security.seconds_until_unlocked() == security.LOCKOUT_SECONDS - 600 + 1
        security.clear_failed_attempts()
        assert security.seconds_until_unlocked() == 0


def test_successful_login_clears_failures(client):
    enable_login()
    for _ in range(security.MAX_FAILED_ATTEMPTS - 1):
        sign_in(client, "nope")
    assert sign_in(client).status_code == 302
    client.post("/logout")
    for _ in range(security.MAX_FAILED_ATTEMPTS - 1):
        assert sign_in(client, "nope").status_code == 401
    assert sign_in(client).status_code == 302


def test_sign_in_starts_a_fresh_session(client):
    enable_login()
    with client.session_transaction() as sess:
        sess["planted"] = "value"
    sign_in(client)
    with client.session_transaction() as sess:
        assert "planted" not in sess
        assert sess["authenticated"] is True
        assert sess["auth_version"] == security.session_version()
        assert sess.permanent is True


# ---------------------------------------------------------------------------
# Logout and nav
# ---------------------------------------------------------------------------

def test_logout_signs_out(client):
    enable_login()
    sign_in(client)
    response = client.post("/logout", follow_redirects=True)
    assert response.request.path == "/login"
    assert b"Signed out" in response.data
    assert client.get("/settings/security/").status_code == 302


def test_logout_when_auth_off_goes_home(client):
    response = client.post("/logout")
    assert response.status_code == 302
    assert path(response) == "/"


def test_nav_shows_sign_out_only_when_signed_in(client):
    page = client.get("/settings/security/")
    assert b"Sign out" not in page.data

    enable_login()
    assert b"Sign out" not in client.get("/login").data
    sign_in(client)
    assert b"Sign out" in client.get("/settings/security/").data


def test_inject_auth_context(client):
    with client.application.test_request_context("/"):
        assert security.inject_auth_context() == {"auth_enabled": False, "signed_in": False, "log_history_enabled": True}
        enable_login()
        assert security.inject_auth_context() == {"auth_enabled": True, "signed_in": False, "log_history_enabled": True}


# ---------------------------------------------------------------------------
# Setting the password
# ---------------------------------------------------------------------------

def test_set_first_password(client):
    response = client.post(
        "/settings/security/password",
        data={"new_password": PASSWORD, "confirm_password": PASSWORD},
        follow_redirects=True,
    )
    assert b"Password saved" in response.data
    assert security.check_password(PASSWORD)
    # Sign in is still off until it's turned on.
    assert security.auth_required() is False


def test_password_too_short(client):
    response = client.post(
        "/settings/security/password",
        data={"new_password": "short", "confirm_password": "short"},
        follow_redirects=True,
    )
    assert b"Use at least 8 characters" in response.data
    assert security.get_setting("auth_password_hash") is None


def test_password_exactly_min_length_is_accepted(client):
    password = "x" * security.MIN_PASSWORD_LENGTH
    client.post("/settings/security/password", data={"new_password": password, "confirm_password": password})
    assert security.check_password(password)


def test_password_mismatch(client):
    response = client.post(
        "/settings/security/password",
        data={"new_password": PASSWORD, "confirm_password": PASSWORD + "!"},
        follow_redirects=True,
    )
    assert b"The passwords don&#39;t match" in response.data
    assert security.get_setting("auth_password_hash") is None


def test_changing_password_needs_current_password(client):
    security.set_password(PASSWORD)
    new = "a brand new password"
    response = client.post(
        "/settings/security/password",
        data={"current_password": "wrong", "new_password": new, "confirm_password": new},
        follow_redirects=True,
    )
    assert b"Current password is incorrect" in response.data
    assert security.check_password(PASSWORD)
    assert not security.check_password(new)

    client.post(
        "/settings/security/password",
        data={"current_password": PASSWORD, "new_password": new, "confirm_password": new},
    )
    assert security.check_password(new)
    assert not security.check_password(PASSWORD)


def test_env_escape_hatch_skips_current_password(client, monkeypatch):
    enable_login()
    monkeypatch.setenv("POT_SYNC_DISABLE_AUTH", "true")
    new = "recovered password"
    response = client.post(
        "/settings/security/password",
        data={"new_password": new, "confirm_password": new},
        follow_redirects=True,
    )
    assert b"Password saved" in response.data
    assert security.check_password(new)


def test_password_change_signs_out_other_sessions_but_keeps_this_one(client):
    enable_login()
    other = client.application.test_client()
    other.post("/login", data={"password": PASSWORD})
    sign_in(client)
    assert other.get("/settings/security/").status_code == 200

    new = "a brand new password"
    client.post(
        "/settings/security/password",
        data={"current_password": PASSWORD, "new_password": new, "confirm_password": new},
    )
    assert client.get("/settings/security/").status_code == 200
    assert path(other.get("/settings/security/")) == "/login"


# ---------------------------------------------------------------------------
# Turning sign in on and off
# ---------------------------------------------------------------------------

def test_unknown_mode_rejected(client):
    response = client.post("/settings/security/mode", data={"mode": "magic"}, follow_redirects=True)
    assert b"Unknown sign in option" in response.data
    assert security.auth_mode() == security.AUTH_MODE_NONE


def test_turning_on_needs_a_password(client):
    response = client.post("/settings/security/mode", data={"mode": "password"}, follow_redirects=True)
    assert b"Set a password before turning on sign in" in response.data
    assert security.auth_mode() == security.AUTH_MODE_NONE


def test_turning_on_needs_current_password(client):
    security.set_password(PASSWORD)
    response = client.post(
        "/settings/security/mode", data={"mode": "password", "current_password": "wrong"}, follow_redirects=True
    )
    assert b"Current password is incorrect" in response.data
    assert security.auth_mode() == security.AUTH_MODE_NONE


def test_turn_on_then_off(client):
    security.set_password(PASSWORD)
    other = client.application.test_client()

    response = client.post(
        "/settings/security/mode", data={"mode": "password", "current_password": PASSWORD}, follow_redirects=True
    )
    assert b"Sign in is on." in response.data
    assert security.auth_required() is True
    # This browser is signed in, others must sign in.
    assert client.get("/settings/security/").status_code == 200
    assert path(other.get("/settings/security/")) == "/login"
    other.post("/login", data={"password": PASSWORD})
    assert other.get("/settings/security/").status_code == 200

    response = client.post(
        "/settings/security/mode", data={"mode": "none", "current_password": PASSWORD}, follow_redirects=True
    )
    assert b"Sign in is off." in response.data
    assert security.auth_mode() == security.AUTH_MODE_NONE
    with client.session_transaction() as sess:
        assert "authenticated" not in sess
    assert client.get("/settings/security/").status_code == 200

    # Turning it back on invalidates the old sign ins from before it was turned off.
    version_before = security.session_version()
    client.post("/settings/security/mode", data={"mode": "password", "current_password": PASSWORD})
    assert security.session_version() != version_before
    assert path(other.get("/settings/security/")) == "/login"
    assert client.get("/settings/security/").status_code == 200


def test_turning_on_keeps_pending_return_path(client):
    security.set_password(PASSWORD)
    with client.session_transaction() as sess:
        sess["next"] = "/accounts/"
        sess["planted"] = "value"
    client.post("/settings/security/mode", data={"mode": "password", "current_password": PASSWORD})
    with client.session_transaction() as sess:
        assert sess["next"] == "/accounts/"
        assert "planted" not in sess
        assert sess["authenticated"] is True


def test_turning_off_needs_current_password(client):
    enable_login()
    sign_in(client)
    client.post("/settings/security/mode", data={"mode": "none", "current_password": "wrong"})
    assert security.auth_mode() == security.AUTH_MODE_PASSWORD


# ---------------------------------------------------------------------------
# Authenticator app (TOTP)
# ---------------------------------------------------------------------------

def test_totp_setup_page_shows_svg_qr_and_keeps_secret(client):
    response = client.get("/settings/security/totp")
    assert response.status_code == 200
    assert b"<svg" in response.data
    with client.session_transaction() as sess:
        secret = sess["pending_totp_secret"]
    assert secret.encode() in response.data
    assert pyotp.TOTP(secret).now()  # a valid base32 secret
    # Reloading the page keeps the same secret so an already scanned QR still works.
    client.get("/settings/security/totp")
    with client.session_transaction() as sess:
        assert sess["pending_totp_secret"] == secret


def test_totp_uri_names_the_app():
    uri = security.totp_uri(TOTP_SECRET)
    assert uri.startswith("otpauth://totp/")
    assert f"secret={TOTP_SECRET}" in uri
    assert "issuer=Monzo%20Credit%20Card%20Pot%20Sync" in uri


def test_totp_enable_with_valid_code(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    client.get("/settings/security/totp")
    with client.session_transaction() as sess:
        secret = sess["pending_totp_secret"]
    code = pyotp.TOTP(secret).at(FIXED_NOW)
    response = client.post("/settings/security/totp", data={"code": code}, follow_redirects=True)
    assert b"Two-factor authentication is on" in response.data
    assert security.totp_enabled()
    assert security.get_setting("auth_totp_secret") == secret
    with client.session_transaction() as sess:
        assert "pending_totp_secret" not in sess
    # Once on, the setup page goes back to Security.
    assert path(client.get("/settings/security/totp")) == "/settings/security/"


def test_totp_enable_rejects_invalid_code(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    client.get("/settings/security/totp")
    with client.session_transaction() as sess:
        secret = sess["pending_totp_secret"]
    wrong = "000000" if pyotp.TOTP(secret).at(FIXED_NOW) != "000000" else "111111"
    response = client.post("/settings/security/totp", data={"code": wrong})
    assert response.status_code == 302
    assert path(response) == "/settings/security/totp"
    assert not security.totp_enabled()


def test_totp_enable_without_pending_secret(client):
    response = client.post("/settings/security/totp", data={"code": "123456"})
    assert path(response) == "/settings/security/totp"
    assert not security.totp_enabled()


def test_totp_disable_needs_current_password(client):
    security.set_password(PASSWORD)
    security.set_setting("auth_totp_secret", TOTP_SECRET)
    response = client.post("/settings/security/totp/disable", data={"current_password": "nope"}, follow_redirects=True)
    assert b"Current password is incorrect" in response.data
    assert security.totp_enabled()

    response = client.post(
        "/settings/security/totp/disable", data={"current_password": PASSWORD}, follow_redirects=True
    )
    assert b"Two-factor authentication is off" in response.data
    assert not security.totp_enabled()


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", None])
def test_verify_totp_rejects_malformed_codes(client, code):
    assert security.verify_totp(TOTP_SECRET, code) is False


def test_verify_totp_without_secret(client):
    assert security.verify_totp(None, "123456") is False


def test_verify_totp_accepts_spaces_and_one_step_of_drift(client, monkeypatch):
    monkeypatch.setattr("app.security.time", lambda: FIXED_NOW)
    totp = pyotp.TOTP(TOTP_SECRET)
    code = totp.at(FIXED_NOW - 30)
    assert security.verify_totp(TOTP_SECRET, f"{code[:3]} {code[3:]}") is True

    security.set_setting("auth_totp_last_step", "-1")
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW + 30)) is True

    security.set_setting("auth_totp_last_step", "-1")
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW - 60)) is False
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW + 60)) is False


def test_verify_totp_refuses_replay_and_older_codes(client, monkeypatch):
    monkeypatch.setattr("app.security.time", lambda: FIXED_NOW)
    totp = pyotp.TOTP(TOTP_SECRET)
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW)) is True
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW)) is False
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW - 30)) is False
    # The next step's code is still fine.
    monkeypatch.setattr("app.security.time", lambda: FIXED_NOW + 30)
    assert security.verify_totp(TOTP_SECRET, totp.at(FIXED_NOW + 30)) is True


# ---------------------------------------------------------------------------
# 2FA sign in step
# ---------------------------------------------------------------------------

def test_two_factor_login(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    client.get("/settings/?x=1")

    response = sign_in(client)
    assert path(response) == "/login/2fa"
    # The password alone doesn't sign in.
    with client.session_transaction() as sess:
        assert "authenticated" not in sess
        assert sess["password_ok_at"] == FIXED_NOW
    assert client.get("/login/2fa").status_code == 200

    response = client.post("/login/2fa", data={"code": pyotp.TOTP(TOTP_SECRET).at(FIXED_NOW)})
    assert response.status_code == 302
    assert full_target(response) == "/settings/?x=1"
    assert client.get("/settings/security/").status_code == 200
    with client.session_transaction() as sess:
        assert "password_ok_at" not in sess


def test_two_factor_wrong_code(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    sign_in(client)
    response = client.post("/login/2fa", data={"code": "abc"})
    assert response.status_code == 401
    assert b"That code didn" in response.data
    assert client.get("/settings/security/").status_code == 302


def test_two_factor_throttled(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    sign_in(client)
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        assert client.post("/login/2fa", data={"code": "000000x"}).status_code == 401
    response = client.post("/login/2fa", data={"code": pyotp.TOTP(TOTP_SECRET).at(FIXED_NOW)})
    assert response.status_code == 429
    assert b"Too many failed attempts" in response.data
    # The password step is locked too.
    assert sign_in(client).status_code == 429


def test_two_factor_window_expires_after_five_minutes(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    sign_in(client)

    freeze_time(monkeypatch, FIXED_NOW + 300)
    assert client.get("/login/2fa").status_code == 200

    later = FIXED_NOW + 301
    freeze_time(monkeypatch, later)
    response = client.post("/login/2fa", data={"code": pyotp.TOTP(TOTP_SECRET).at(later)})
    assert path(response) == "/login"
    with client.session_transaction() as sess:
        assert "password_ok_at" not in sess
        assert "authenticated" not in sess


def test_two_factor_code_replay_refused(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    code = pyotp.TOTP(TOTP_SECRET).at(FIXED_NOW)
    sign_in(client)
    assert client.post("/login/2fa", data={"code": code}).status_code == 302

    other = client.application.test_client()
    other.post("/login", data={"password": PASSWORD})
    assert other.post("/login/2fa", data={"code": code}).status_code == 401


def test_two_factor_accepts_one_step_clock_drift(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    enable_login(totp_secret=TOTP_SECRET)
    sign_in(client)
    response = client.post("/login/2fa", data={"code": pyotp.TOTP(TOTP_SECRET).at(FIXED_NOW - 30)})
    assert response.status_code == 302
    assert path(response) == "/"


def test_two_factor_page_needs_auth_enabled(client, monkeypatch):
    freeze_time(monkeypatch, FIXED_NOW)
    with client.session_transaction() as sess:
        sess["password_ok_at"] = FIXED_NOW
    response = client.get("/login/2fa")
    assert path(response) == "/login"


# ---------------------------------------------------------------------------
# Session signing key
# ---------------------------------------------------------------------------

def test_persistent_secret_key_generated_once(client):
    assert security.get_setting("secret_key") is None
    key = security.persistent_secret_key()
    assert len(key) == 64
    int(key, 16)
    assert security.get_setting("secret_key") == key
    assert security.persistent_secret_key() == key


def test_explicit_secret_key_is_used_and_nothing_is_stored(client):
    assert client.application.config["SECRET_KEY"] == "testing"
    assert security.get_setting("secret_key") is None


def test_create_app_uses_persistent_key_without_secret_key(tmp_path):
    uri = f"sqlite:///{tmp_path / 'app.db'}"
    first = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri})
    key = first.config["SECRET_KEY"]
    assert key and key != "testing" and len(key) == 64
    with first.app_context():
        assert security.get_setting("secret_key") == key
        db.session.remove()

    second = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "SECRET_KEY": None})
    assert second.config["SECRET_KEY"] == key
    with second.app_context():
        db.session.remove()
        db.engine.dispose()
    with first.app_context():
        db.engine.dispose()
