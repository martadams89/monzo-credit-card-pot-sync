"""Tests for passkey (WebAuthn) registration, sign in and the origin checks."""

from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
from webauthn.helpers import bytes_to_base64url

from app import security
from app.extensions import db
from app.models.passkey import PasskeyModel

PASSWORD = "correct horse battery"


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


def enable_login():
    security.set_password(PASSWORD)
    security.set_setting("auth_mode", security.AUTH_MODE_PASSWORD)


def add_passkey(credential_id="Y3JlZC0x", name="Phone", sign_count=3):
    passkey = PasskeyModel(
        credential_id=credential_id, public_key=b"public-key", sign_count=sign_count, name=name, created_at=1000
    )
    db.session.add(passkey)
    db.session.commit()
    return passkey


def all_passkeys():
    db.session.expire_all()
    return db.session.query(PasskeyModel).order_by(PasskeyModel.id).all()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_registration_options(client):
    add_passkey(credential_id=bytes_to_base64url(b"existing-cred"))
    response = client.post("/settings/security/passkeys/options")
    assert response.status_code == 200
    options = response.get_json()
    assert options["rp"] == {"id": "pots.example.com", "name": "Monzo Credit Card Pot Sync"}
    assert options["user"]["name"] == "pot-sync"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["requireResidentKey"] is True
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert [c["id"] for c in options["excludeCredentials"]] == [bytes_to_base64url(b"existing-cred")]
    with client.session_transaction() as sess:
        assert sess["passkey_registration_challenge"] == options["challenge"]

    # The user handle is created once and reused, so all passkeys belong to one user.
    assert security.get_setting("auth_user_handle") == options["user"]["id"]
    again = client.post("/settings/security/passkeys/options").get_json()
    assert again["user"]["id"] == options["user"]["id"]
    assert again["challenge"] != options["challenge"]


def test_register_without_challenge(client, mocker):
    verify = mocker.patch("webauthn.verify_registration_response")
    response = client.post("/settings/security/passkeys", json={"credential": {}})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Start adding the passkey again"}
    verify.assert_not_called()
    assert all_passkeys() == []


def test_register_verification_failure(client, mocker):
    mocker.patch("webauthn.verify_registration_response", side_effect=ValueError("bad attestation"))
    client.post("/settings/security/passkeys/options")
    response = client.post("/settings/security/passkeys", json={"credential": {"id": "x"}, "name": "Laptop"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "The passkey couldn't be verified"}
    assert all_passkeys() == []
    # The challenge is single use.
    with client.session_transaction() as sess:
        assert "passkey_registration_challenge" not in sess


def test_register_success(client, mocker):
    verify = mocker.patch(
        "webauthn.verify_registration_response",
        return_value=SimpleNamespace(credential_id=b"new-cred", credential_public_key=b"pk-bytes", sign_count=7),
    )
    options = client.post("/settings/security/passkeys/options").get_json()
    credential = {"id": "bmV3LWNyZWQ", "response": {}}
    response = client.post(
        "/settings/security/passkeys", json={"credential": credential, "name": "  Laptop  "}
    )
    assert response.status_code == 200
    assert response.get_json() == {"redirect": "/settings/security/"}

    kwargs = verify.call_args.kwargs
    assert kwargs["credential"] == credential
    assert bytes_to_base64url(kwargs["expected_challenge"]) == options["challenge"]
    assert kwargs["expected_rp_id"] == "pots.example.com"
    assert "https://pots.example.com" in kwargs["expected_origin"]
    assert kwargs["require_user_verification"] is True

    [passkey] = all_passkeys()
    assert passkey.credential_id == bytes_to_base64url(b"new-cred")
    assert passkey.public_key == b"pk-bytes"
    assert passkey.sign_count == 7
    assert passkey.name == "Laptop"
    assert passkey.created_at > 0
    assert passkey.last_used_at is None
    page = client.get("/settings/security/")
    assert b"Passkey &#34;Laptop&#34; added" in page.data or b"Passkey &quot;Laptop&quot; added" in page.data
    assert b"Laptop" in page.data

    # A second submission with the used challenge is refused.
    assert client.post("/settings/security/passkeys", json={"credential": credential}).status_code == 400


def test_register_default_and_truncated_names(client, mocker):
    results = iter([
        SimpleNamespace(credential_id=b"one", credential_public_key=b"pk", sign_count=0),
        SimpleNamespace(credential_id=b"two", credential_public_key=b"pk", sign_count=0),
    ])
    mocker.patch("webauthn.verify_registration_response", side_effect=lambda **_: next(results))
    client.post("/settings/security/passkeys/options")
    client.post("/settings/security/passkeys", json={"credential": {}, "name": "   "})
    client.post("/settings/security/passkeys/options")
    client.post("/settings/security/passkeys", json={"credential": {}, "name": "n" * 150})
    names = [p.name for p in all_passkeys()]
    assert names == ["Passkey 1", "n" * 100]


def test_register_with_non_json_body(client, mocker):
    verify = mocker.patch("webauthn.verify_registration_response", side_effect=ValueError("empty"))
    client.post("/settings/security/passkeys/options")
    response = client.post("/settings/security/passkeys", data="not json")
    assert response.status_code == 400
    assert verify.call_args.kwargs["credential"] == {}


def test_delete_passkey(client):
    keep = add_passkey(credential_id="a", name="Keep")
    remove = add_passkey(credential_id="b", name="Remove")
    response = client.post(f"/settings/security/passkeys/{remove.id}/delete", follow_redirects=True)
    assert response.request.path == "/settings/security/"
    assert b"Passkey &#34;Remove&#34; removed" in response.data or b"Passkey &quot;Remove&quot; removed" in response.data
    assert [p.id for p in all_passkeys()] == [keep.id]


def test_delete_unknown_passkey(client):
    add_passkey()
    response = client.post("/settings/security/passkeys/999/delete")
    assert response.status_code == 302
    assert urlparse(response.location).path == "/settings/security/"
    assert len(all_passkeys()) == 1


# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------

def test_authentication_options_need_auth_enabled(client):
    response = client.post("/login/passkey/options")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Sign in is not enabled"}


def test_authentication_options(client):
    enable_login()
    response = client.post("/login/passkey/options")
    assert response.status_code == 200
    options = response.get_json()
    assert options["rpId"] == "pots.example.com"
    assert options["userVerification"] == "required"
    # Discoverable credentials: the browser picks the passkey, so none are listed.
    assert options.get("allowCredentials", []) == []
    with client.session_transaction() as sess:
        assert sess["passkey_challenge"] == options["challenge"]


def test_verify_without_challenge(client, mocker):
    enable_login()
    verify = mocker.patch("webauthn.verify_authentication_response")
    response = client.post("/login/passkey/verify", json={"id": "Y3JlZC0x"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Start the passkey sign in again"}
    verify.assert_not_called()


def test_verify_when_auth_disabled(client, mocker):
    add_passkey()
    verify = mocker.patch("webauthn.verify_authentication_response")
    with client.session_transaction() as sess:
        sess["passkey_challenge"] = bytes_to_base64url(b"challenge")
    response = client.post("/login/passkey/verify", json={"id": "Y3JlZC0x"})
    assert response.status_code == 400
    verify.assert_not_called()


def test_verify_unknown_credential(client, mocker):
    enable_login()
    add_passkey()
    verify = mocker.patch("webauthn.verify_authentication_response")
    client.post("/login/passkey/options")
    response = client.post("/login/passkey/verify", json={"id": "not-registered"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "This passkey isn't registered here"}
    verify.assert_not_called()
    assert security._failures["127.0.0.1"]


def test_verify_failure(client, mocker):
    enable_login()
    add_passkey()
    mocker.patch("webauthn.verify_authentication_response", side_effect=ValueError("bad signature"))
    client.post("/login/passkey/options")
    response = client.post("/login/passkey/verify", json={"id": "Y3JlZC0x"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Passkey sign in failed"}
    [passkey] = all_passkeys()
    assert passkey.sign_count == 3
    assert passkey.last_used_at is None
    assert client.get("/settings/security/").status_code == 302


def test_verify_success(client, mocker):
    enable_login()
    add_passkey(sign_count=3)
    verify = mocker.patch(
        "webauthn.verify_authentication_response", return_value=SimpleNamespace(new_sign_count=4)
    )
    client.get("/settings/?from=passkey")
    options = client.post("/login/passkey/options").get_json()
    credential = {"id": "Y3JlZC0x", "response": {}}
    response = client.post("/login/passkey/verify", json=credential)
    assert response.status_code == 200
    assert response.get_json() == {"redirect": "/settings/?from=passkey"}

    kwargs = verify.call_args.kwargs
    assert kwargs["credential"] == credential
    assert bytes_to_base64url(kwargs["expected_challenge"]) == options["challenge"]
    assert kwargs["expected_rp_id"] == "pots.example.com"
    assert kwargs["credential_public_key"] == b"public-key"
    assert kwargs["credential_current_sign_count"] == 3
    assert kwargs["require_user_verification"] is True

    [passkey] = all_passkeys()
    assert passkey.sign_count == 4
    assert passkey.last_used_at is not None and passkey.last_used_at > 0
    assert client.get("/settings/security/").status_code == 200

    # The challenge can't be reused.
    client.post("/logout")
    assert client.post("/login/passkey/verify", json=credential).status_code == 400


def test_verify_locked_out(client, mocker):
    enable_login()
    add_passkey()
    verify = mocker.patch("webauthn.verify_authentication_response")
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        client.post("/login", data={"password": "nope"})
    client.post("/login/passkey/options")
    response = client.post("/login/passkey/verify", json={"id": "Y3JlZC0x"})
    assert response.status_code == 429
    assert "Too many failed attempts" in response.get_json()["error"]
    verify.assert_not_called()


# ---------------------------------------------------------------------------
# Relying party and origins
# ---------------------------------------------------------------------------

def origins_for(client, base_url, local_url="https://pots.example.com"):
    client.application.config["LOCAL_URL"] = local_url
    with client.application.test_request_context("/", base_url=base_url):
        return security.webauthn_expected_origins()


def test_origins_configured_url_only_for_other_hosts(client):
    assert origins_for(client, "http://attacker.example.net") == ["https://pots.example.com"]
    # A host that merely ends with the domain name isn't a subdomain.
    assert origins_for(client, "https://evilpots.example.com") == ["https://pots.example.com"]


def test_origins_include_request_host_when_it_is_the_rp_id(client):
    assert origins_for(client, "https://pots.example.com:8443") == [
        "http://pots.example.com:8443",
        "https://pots.example.com",
        "https://pots.example.com:8443",
    ]


def test_origins_include_subdomain_host(client):
    assert origins_for(client, "https://a.pots.example.com") == [
        "http://a.pots.example.com",
        "https://a.pots.example.com",
        "https://pots.example.com",
    ]


def test_origins_keep_configured_port(client):
    assert origins_for(client, "http://192.168.1.2:1337", "http://localhost:1337") == ["http://localhost:1337"]
    assert origins_for(client, "http://localhost:1337", "http://localhost:1337") == [
        "http://localhost:1337",
        "https://localhost:1337",
    ]


def test_rp_id(client):
    with client.application.test_request_context("/"):
        assert security.webauthn_rp_id() == "pots.example.com"
        client.application.config["LOCAL_URL"] = "https://Pots.Example.com:8443/app"
        assert security.webauthn_rp_id() == "pots.example.com"
        client.application.config["LOCAL_URL"] = ""
        assert security.webauthn_rp_id() == "localhost"
