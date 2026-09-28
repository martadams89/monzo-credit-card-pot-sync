"""Per-card cooldown (POST /accounts/cooldown), reconnecting a card
(GET /accounts/reconnect/<type>) and the TrueLayer callback's reconnect path."""

from time import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.domain.accounts import TrueLayerAccount
from app.domain.auth_providers import AuthProviderType
from app.domain.settings import Setting
from app.extensions import db
from app.models.account import AccountModel
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository

AMEX = AuthProviderType.AMEX.value
TRUELAYER_TOKEN_URL = "https://auth.truelayer.com/connect/token"


def _account(account_type):
    return AccountModel.query.filter_by(type=account_type).one_or_none()


def _set_fields(account_type, **fields):
    record = AccountModel.query.filter_by(type=account_type).one()
    for field, value in fields.items():
        setattr(record, field, value)
    db.session.commit()


def _flashes(test_client):
    with test_client.session_transaction() as session:
        return session.get("_flashes", [])


def _redirects_to_accounts(response):
    assert response.status_code == 302
    assert urlparse(response.location).path == "/accounts/"


@pytest.fixture
def client_ids(test_client):
    repository = SqlAlchemySettingRepository(db)
    repository.save(Setting("truelayer_client_id", "tl_client"))
    repository.save(Setting("truelayer_client_secret", "tl_secret"))
    repository.save(Setting("monzo_client_id", "monzo_client"))


# ---------------------------------------------------------------------------
# POST /accounts/cooldown
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "12", "720", " 48 "])
def test_valid_cooldown_is_saved(test_client, seed_data, value):
    response = test_client.post("/accounts/cooldown", data={"account_type": AMEX, "cooldown_hours": value})

    _redirects_to_accounts(response)
    hours = int(value)
    assert _account(AMEX).cooldown_hours == hours
    assert _flashes(test_client) == [("message", f"{AMEX} cooldown set to {hours} hours")]


@pytest.mark.parametrize("data", [{"cooldown_hours": ""}, {"cooldown_hours": "   "}, {}])
def test_blank_cooldown_reverts_to_the_default(test_client, seed_data, data):
    _set_fields(AMEX, cooldown_hours=24)

    response = test_client.post("/accounts/cooldown", data={"account_type": AMEX, **data})

    _redirects_to_accounts(response)
    assert _account(AMEX).cooldown_hours is None
    assert _flashes(test_client) == [("message", f"{AMEX} now uses the default cooldown")]


@pytest.mark.parametrize("value", ["0", "-5", "721", "abc", "2.5", "1e3"])
def test_invalid_cooldown_is_rejected_and_nothing_changes(test_client, seed_data, value):
    _set_fields(AMEX, cooldown_hours=24)

    response = test_client.post("/accounts/cooldown", data={"account_type": AMEX, "cooldown_hours": value})

    _redirects_to_accounts(response)
    assert _account(AMEX).cooldown_hours == 24
    assert _flashes(test_client) == [("error", "Cooldown must be between 1 and 720 hours")]


def test_cooldown_for_unknown_account(test_client, seed_data):
    response = test_client.post("/accounts/cooldown", data={"account_type": "Nope", "cooldown_hours": "5"})

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("error", "Account not found")]
    assert _account(AMEX).cooldown_hours is None


def test_cooldown_only_changes_the_selected_connection(test_client, seed_data):
    SqlAlchemyAccountRepository(db).save(
        TrueLayerAccount(f"{AMEX} 2", "a", "r", int(time()) + 1000, "pot_2", provider_type=AMEX)
    )

    test_client.post("/accounts/cooldown", data={"account_type": f"{AMEX} 2", "cooldown_hours": "6"})

    assert _account(f"{AMEX} 2").cooldown_hours == 6
    assert _account(AMEX).cooldown_hours is None


def test_accounts_page_shows_the_cooldown_and_default(test_client, seed_data):
    SqlAlchemySettingRepository(db).save(Setting("deposit_cooldown_hours", "4"))
    _set_fields(AMEX, cooldown_hours=36)

    html = test_client.get("/accounts/").data.decode()

    assert 'value="36"' in html
    assert "Default (4)" in html
    assert 'href="/accounts/reconnect/American%20Express"' in html


# ---------------------------------------------------------------------------
# GET /accounts/reconnect/<type>
# ---------------------------------------------------------------------------


def test_reconnect_sends_the_user_to_the_card_provider(test_client, seed_data, client_ids):
    response = test_client.get("/accounts/reconnect/American%20Express")

    assert response.status_code == 302
    location = urlparse(response.location)
    assert f"{location.scheme}://{location.netloc}" == "https://auth.truelayer.com"
    params = parse_qs(location.query)
    assert params["providers"] == ["uk-ob-amex"]
    assert params["client_id"] == ["tl_client"]
    assert params["state"][0].startswith(f"{AMEX}-")
    with test_client.session_transaction() as session:
        # Bound to this sign-in attempt's state, so only its callback can use it.
        assert session["reconnect"] == {"account": AMEX, "state": params["state"][0]}


def test_reconnect_a_second_connection_of_the_same_provider(test_client, seed_data, client_ids):
    SqlAlchemyAccountRepository(db).save(
        TrueLayerAccount(f"{AMEX} 2", "a", "r", int(time()) + 1000, "pot_2", provider_type=AMEX)
    )

    response = test_client.get("/accounts/reconnect/American%20Express%202")

    assert parse_qs(urlparse(response.location).query)["providers"] == ["uk-ob-amex"]
    with test_client.session_transaction() as session:
        assert session["reconnect"]["account"] == f"{AMEX} 2"


def test_reconnect_unknown_account(test_client, seed_data):
    response = test_client.get("/accounts/reconnect/Nope")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("error", "Account not found")]
    with test_client.session_transaction() as session:
        assert "reconnect" not in session


def test_reconnect_account_with_unknown_provider(test_client, seed_data):
    # A connection whose provider this version no longer supports.
    db.session.add(AccountModel(type="Old Bank", provider="Old Bank", access_token="a", refresh_token="r"))
    db.session.commit()

    response = test_client.get("/accounts/reconnect/Old%20Bank")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("error", "Account not found")]
    with test_client.session_transaction() as session:
        assert "reconnect" not in session


# ---------------------------------------------------------------------------
# TrueLayer callback: reconnect path
# ---------------------------------------------------------------------------


def _token_response(requests_mock, access="new_access", refresh="new_refresh", expires_in=3600):
    requests_mock.post(
        TRUELAYER_TOKEN_URL,
        json={"access_token": access, "refresh_token": refresh, "expires_in": expires_in},
    )


def _start_reconnect(test_client, account_type, state="American Express-123"):
    with test_client.session_transaction() as session:
        session["reconnect"] = {"account": account_type, "state": state}


def test_reconnect_callback_updates_the_existing_connection(test_client, seed_data, requests_mock):
    _set_fields(
        AMEX,
        pot_id="amex_pot",
        cooldown_until=int(time()) + 3600,
        cooldown_ref_card_balance=5000,
        prev_balance=4200,
        include_pending_credits=False,
        cooldown_hours=12,
        consent_expires_at=int(time()) - 60,
        consent_reminder_sent_at=int(time()) - 600,
    )
    before = _account(AMEX)
    account_id, row_id = before.account_id, before.id
    _token_response(requests_mock)
    _start_reconnect(test_client, AMEX)

    response = test_client.get("/auth/callback/truelayer?code=abc&state=American%20Express-123")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("message", f"Reconnected {AMEX}")]
    assert AccountModel.query.filter(AccountModel.type != "Monzo").count() == 1
    assert _account(f"{AMEX} 2") is None
    amex = _account(AMEX)
    assert amex.id == row_id
    assert amex.access_token == "new_access"
    assert amex.refresh_token == "new_refresh"
    assert int(time()) + 3500 <= amex.token_expiry <= int(time()) + 3600
    # Everything else about the connection is kept.
    assert amex.pot_id == "amex_pot"
    assert amex.account_id == account_id
    assert amex.prev_balance == 4200
    assert amex.cooldown_until is not None
    assert amex.cooldown_ref_card_balance == 5000
    assert amex.include_pending_credits is False
    assert amex.cooldown_hours == 12
    # The old consent no longer applies; the next sync reads the new one.
    assert amex.consent_expires_at is None
    assert amex.consent_reminder_sent_at is None
    with test_client.session_transaction() as session:
        assert "reconnect" not in session
    assert parse_qs(requests_mock.last_request.text)["code"] == ["abc"]


def test_reconnect_callback_for_a_numbered_connection(test_client, seed_data, requests_mock):
    SqlAlchemyAccountRepository(db).save(
        TrueLayerAccount(f"{AMEX} 2", "old", "old", int(time()) + 1000, "pot_2", provider_type=AMEX)
    )
    _token_response(requests_mock)
    _start_reconnect(test_client, f"{AMEX} 2")

    test_client.get("/auth/callback/truelayer?code=abc&state=American%20Express-123")

    assert _account(f"{AMEX} 2").access_token == "new_access"
    assert _account(AMEX).access_token == "access_token"
    assert _account(f"{AMEX} 3") is None


def test_reconnect_with_a_different_provider_adds_a_new_connection(test_client, seed_data, requests_mock):
    # Reconnect was started for Amex but the user came back from Barclaycard.
    _token_response(requests_mock)
    _start_reconnect(test_client, AMEX)

    response = test_client.get("/auth/callback/truelayer?code=abc&state=Barclaycard-123")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("message", "Successfully linked Barclaycard")]
    assert _account(AMEX).access_token == "access_token"
    barclaycard = _account("Barclaycard")
    assert barclaycard.access_token == "new_access"
    assert barclaycard.provider == "Barclaycard"
    assert barclaycard.pot_id == "default_pot"
    with test_client.session_transaction() as session:
        assert "reconnect" not in session


def test_reconnect_of_a_deleted_account_adds_a_new_connection(test_client, seed_data, requests_mock):
    # The connection was removed while the user was at their bank.
    _token_response(requests_mock)
    _start_reconnect(test_client, AMEX)
    AccountModel.query.filter_by(type=AMEX).delete()
    db.session.commit()

    response = test_client.get("/auth/callback/truelayer?code=abc&state=American%20Express-123")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("message", f"Successfully linked {AMEX}")]
    amex = _account(AMEX)
    assert amex.access_token == "new_access"
    assert amex.pot_id == "default_pot"
    with test_client.session_transaction() as session:
        assert "reconnect" not in session


def test_callback_without_reconnect_still_adds_a_numbered_connection(test_client, seed_data, requests_mock):
    _token_response(requests_mock)

    test_client.get("/auth/callback/truelayer?code=abc&state=American%20Express-123")

    assert _account(AMEX).access_token == "access_token"
    assert _account(f"{AMEX} 2").access_token == "new_access"


def test_full_reconnect_flow(test_client, seed_data, client_ids, requests_mock):
    _set_fields(AMEX, pot_id="amex_pot")
    start = test_client.get("/accounts/reconnect/American%20Express")
    state = parse_qs(urlparse(start.location).query)["state"][0]
    _token_response(requests_mock, access="fresh")

    test_client.get("/auth/callback/truelayer", query_string={"code": "xyz", "state": state})

    assert _account(AMEX).access_token == "fresh"
    assert _account(AMEX).pot_id == "amex_pot"
    assert _account(f"{AMEX} 2") is None


def test_abandoned_reconnect_does_not_hijack_a_later_add(test_client, seed_data, requests_mock):
    # Reconnect was started for Amex and abandoned at the bank. Adding another Amex
    # card later (a new sign-in attempt, so a different OAuth state) must create a
    # new connection, not overwrite the first card's tokens.
    _token_response(requests_mock)
    _start_reconnect(test_client, AMEX, state="American Express-111")

    response = test_client.get("/auth/callback/truelayer?code=abc&state=American%20Express-222")

    _redirects_to_accounts(response)
    assert _account(AMEX).access_token == "access_token"
    assert _account(f"{AMEX} 2").access_token == "new_access"
    with test_client.session_transaction() as session:
        assert "reconnect" not in session


def test_reconnect_is_not_offered_for_monzo(test_client, seed_data):
    response = test_client.get("/accounts/reconnect/Monzo")

    _redirects_to_accounts(response)
    assert _flashes(test_client) == [("error", "Account not found")]
    with test_client.session_transaction() as session:
        assert "reconnect" not in session
