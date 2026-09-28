"""Hardening: malformed passkey requests, current password for passkey changes,
and trusted reverse-proxy headers for per-visitor sign-in throttling."""

import pytest

from app import create_app, security
from app.extensions import db
from app.models.passkey import PasskeyModel

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("POT_SYNC_DISABLE_AUTH", raising=False)
    monkeypatch.delenv("POT_SYNC_TRUSTED_PROXIES", raising=False)
    security.reset_throttle()
    yield
    security.reset_throttle()


@pytest.fixture
def client(test_client):
    test_client.application.config["LOCAL_URL"] = "https://pots.example.com"
    return test_client


def _signed_in_with_password(client):
    security.set_password(PASSWORD)
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    client.post("/login", data={"password": PASSWORD})


def _add_passkey():
    passkey = PasskeyModel(credential_id="Y3JlZC0x", public_key=b"k", sign_count=0, name="Phone", created_at=1)
    db.session.add(passkey)
    db.session.commit()
    return passkey.id


@pytest.mark.parametrize("body", [[1], "a string", 5])
def test_passkey_sign_in_with_non_object_json_fails_cleanly(client, body):
    security.set_password(PASSWORD)
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    client.post("/login/passkey/options")

    response = client.post("/login/passkey/verify", json=body)

    assert response.status_code == 401
    assert response.get_json() == {"error": "This passkey isn't registered here"}


def test_passkey_register_with_non_object_json_fails_cleanly(client):
    client.post("/settings/security/passkeys/options")
    response = client.post("/settings/security/passkeys", json=[1])
    assert response.status_code == 400


def test_adding_a_passkey_needs_the_current_password(client):
    # A stolen session must not be able to add a passkey that survives a password change.
    _signed_in_with_password(client)

    missing = client.post("/settings/security/passkeys/options", json={})
    wrong = client.post("/settings/security/passkeys/options", json={"current_password": "nope"})
    right = client.post("/settings/security/passkeys/options", json={"current_password": PASSWORD})

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert wrong.get_json() == {"error": "Current password is incorrect"}
    assert right.status_code == 200
    assert "challenge" in right.get_json()


def test_wrong_passwords_for_passkeys_are_throttled(client):
    _signed_in_with_password(client)
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        client.post("/settings/security/passkeys/options", json={"current_password": "nope"})

    response = client.post("/settings/security/passkeys/options", json={"current_password": PASSWORD})

    assert response.status_code == 429


def test_security_page_asks_for_the_password_for_passkeys_only_when_one_is_set(client):
    assert b'id="passkey-password"' not in client.get("/settings/security/").data
    _signed_in_with_password(client)
    assert b'id="passkey-password"' in client.get("/settings/security/").data


def test_escape_hatch_skips_the_password_for_passkeys(client, monkeypatch):
    security.set_password(PASSWORD)
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    monkeypatch.setenv("POT_SYNC_DISABLE_AUTH", "true")

    assert client.post("/settings/security/passkeys/options", json={}).status_code == 200


def test_removing_a_passkey_needs_the_current_password(client):
    _signed_in_with_password(client)
    passkey_id = _add_passkey()

    response = client.post(f"/settings/security/passkeys/{passkey_id}/delete", data={"current_password": "nope"}, follow_redirects=True)
    assert b"Current password is incorrect" in response.data
    assert db.session.get(PasskeyModel, passkey_id) is not None

    client.post(f"/settings/security/passkeys/{passkey_id}/delete", data={"current_password": PASSWORD})
    db.session.expire_all()
    assert db.session.get(PasskeyModel, passkey_id) is None


def _proxied_app(monkeypatch, proxies):
    if proxies is not None:
        monkeypatch.setenv("POT_SYNC_TRUSTED_PROXIES", proxies)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "SECRET_KEY": "t"})
    with app.app_context():
        security.set_password(PASSWORD)
        security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)
    return app


def _lock_out(client, forwarded_for):
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        client.post("/login", data={"password": "nope"}, headers={"X-Forwarded-For": forwarded_for})


def test_trusted_proxy_throttles_each_visitor_separately(monkeypatch):
    app = _proxied_app(monkeypatch, "1")
    client = app.test_client()
    with app.app_context():
        _lock_out(client, "203.0.113.1")

        attacker = client.post("/login", data={"password": PASSWORD}, headers={"X-Forwarded-For": "203.0.113.1"})
        owner = client.post("/login", data={"password": PASSWORD}, headers={"X-Forwarded-For": "198.51.100.7"})

    assert attacker.status_code == 429
    assert owner.status_code == 302


@pytest.mark.parametrize("proxies", [None, "0", "not a number"])
def test_forwarded_headers_are_ignored_unless_trusted(monkeypatch, proxies):
    # Without a trusted proxy, X-Forwarded-For can't be used to dodge the throttle.
    app = _proxied_app(monkeypatch, proxies)
    client = app.test_client()
    with app.app_context():
        _lock_out(client, "203.0.113.1")

        response = client.post("/login", data={"password": PASSWORD}, headers={"X-Forwarded-For": "198.51.100.7"})

    assert response.status_code == 429
