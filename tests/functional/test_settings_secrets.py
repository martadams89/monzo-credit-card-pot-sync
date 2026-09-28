"""The settings form never sends secrets back to the browser, keeps a saved secret
when its field is left blank, and only saves the settings it shows."""

from app import security
from app.web.settings import SECRET_SETTINGS, TEXT_SETTINGS


def save_settings(**settings):
    for key, value in settings.items():
        security.set_setting(key, value)


def test_secrets_are_never_rendered(test_client):
    save_settings(
        monzo_client_id="monzo-id-123",
        monzo_client_secret="monzo-secret-xyz",
        truelayer_client_id="tl-id-456",
        truelayer_client_secret="tl-secret-abc",
    )
    response = test_client.get("/settings/")
    assert response.status_code == 200
    assert b"monzo-id-123" in response.data
    assert b"tl-id-456" in response.data
    assert b"monzo-secret-xyz" not in response.data
    assert b"tl-secret-abc" not in response.data
    assert response.data.count(b"Saved (leave blank to keep)") == 2
    assert b"Not set" not in response.data


def test_unset_secrets_show_not_set(test_client):
    save_settings(monzo_client_secret="only-monzo")
    response = test_client.get("/settings/")
    assert response.data.count(b"Saved (leave blank to keep)") == 1
    assert response.data.count(b"Not set") == 1
    assert b"only-monzo" not in response.data


def test_internal_settings_are_not_rendered(test_client):
    save_settings(auth_password_hash="scrypt:hash-value", secret_key="session-key-value", auth_totp_secret="TOTPSECRET")
    response = test_client.get("/settings/")
    assert b"hash-value" not in response.data
    assert b"session-key-value" not in response.data
    assert b"TOTPSECRET" not in response.data


def test_blank_secret_keeps_saved_value(test_client):
    save_settings(monzo_client_secret="keep-me", truelayer_client_secret="keep-me-too")
    response = test_client.post(
        "/settings/",
        data={"monzo_client_id": "new-id", "monzo_client_secret": "", "truelayer_client_secret": ""},
        follow_redirects=True,
    )
    assert b"Settings saved" in response.data
    assert security.get_setting("monzo_client_id") == "new-id"
    assert security.get_setting("monzo_client_secret") == "keep-me"
    assert security.get_setting("truelayer_client_secret") == "keep-me-too"


def test_non_blank_secret_is_saved(test_client):
    save_settings(monzo_client_secret="old", truelayer_client_secret="old-tl")
    test_client.post("/settings/", data={"monzo_client_secret": "new", "truelayer_client_secret": ""})
    assert security.get_setting("monzo_client_secret") == "new"
    assert security.get_setting("truelayer_client_secret") == "old-tl"


def test_only_whitelisted_text_settings_are_saved(test_client):
    # Sign in stays off here, so the form is reachable without signing in.
    save_settings(auth_password_hash="original-hash", secret_key="original-key")
    response = test_client.post(
        "/settings/",
        data={
            "deposit_cooldown_hours": "5",
            "log_retention_days": "30",
            "auth_mode": "password",
            "auth_password_hash": "attacker-hash",
            "auth_totp_secret": "ATTACKER",
            "secret_key": "attacker-key",
            "made_up_setting": "value",
        },
    )
    assert response.status_code == 302
    assert security.get_setting("deposit_cooldown_hours") == "5"
    assert security.get_setting("log_retention_days") == "30"
    assert security.get_setting("auth_mode") is None
    assert security.get_setting("auth_password_hash") == "original-hash"
    assert security.get_setting("secret_key") == "original-key"
    assert security.get_setting("auth_totp_secret") is None
    assert security.get_setting("made_up_setting") is None


def test_checkboxes_are_saved_and_not_treated_as_text(test_client):
    test_client.post("/settings/", data={"enable_sync": "on"})
    assert security.get_setting("enable_sync") is True
    assert security.get_setting("override_cooldown_spending") is False


def test_sync_interval_change_reschedules(test_client, mocker):
    save_settings(sync_interval_seconds="120")
    modify_job = mocker.patch("app.web.settings.scheduler.modify_job")
    test_client.post("/settings/", data={"sync_interval_seconds": "120"})
    modify_job.assert_not_called()
    test_client.post("/settings/", data={"sync_interval_seconds": "300"})
    modify_job.assert_called_once_with(id="sync_balance", trigger="interval", seconds=300)
    assert security.get_setting("sync_interval_seconds") == "300"


def test_secret_settings_are_a_subset_of_text_settings():
    assert set(SECRET_SETTINGS) <= set(TEXT_SETTINGS)
