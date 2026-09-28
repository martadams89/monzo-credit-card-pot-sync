"""Scenario tests for the branches of the sync loop in ``app.core`` that the main
``test_core.py`` flows do not reach: connection failures, early exits, cooldown
edge cases, the override branch, insufficient funds and database errors.
"""

import logging
from time import time
from urllib.parse import parse_qs

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app import core
from app.core import sync_balance
from app.domain.auth_providers import AuthProviderType
from app.domain.settings import Setting
from app.extensions import db
from app.models.account import AccountModel
from app.models.setting_repository import SqlAlchemySettingRepository

AMEX = AuthProviderType.AMEX.value
MONZO_TOKEN_URL = "https://api.monzo.com/oauth2/token"
TRUELAYER_TOKEN_URL = "https://auth.truelayer.com/connect/token"


class _Pot:
    """A pot whose balance moves with the transfers the sync makes against it."""

    def __init__(self, balance):
        self.balance = balance
        self.deposits = []
        self.withdrawals = []

    def deposit(self, request, context):
        amount = int(parse_qs(request.text)["amount"][0])
        self.deposits.append(amount)
        self.balance += amount
        return {"status": "ok"}

    def withdraw(self, request, context):
        amount = int(parse_qs(request.text)["amount"][0])
        self.withdrawals.append(amount)
        self.balance -= amount
        return {"status": "ok"}


class _Card:
    """A card whose balance (in pounds) can be changed part way through a run.

    ``on_request`` is called with the 1-based count of balance requests before the
    balance is returned, so a test can simulate something happening between the
    steps of a single sync run (a payment landing, a pot being raided).
    """

    def __init__(self, balance, on_request=None):
        self.balance = balance
        self.requests = 0
        self.on_request = on_request

    def respond(self, request, context):
        self.requests += 1
        if self.on_request is not None:
            self.on_request(self.requests)
        return {"results": [{"current": self.balance}]}


def _mock_sync_endpoints(requests_mock, *, pot_balance, card_balance, monzo_balance=1000000, on_card_request=None):
    """Wire up the Monzo and TrueLayer calls a sync run makes.

    ``pot_balance`` is in pence to match the Monzo API; ``card_balance`` is in pounds
    to match TrueLayer.
    """
    pot = _Pot(pot_balance)
    card = _Card(card_balance, on_card_request)

    requests_mock.get("https://api.monzo.com/ping/whoami")
    requests_mock.get("https://api.truelayer.com/data/v1/me")
    requests_mock.get(
        "https://api.monzo.com/pots",
        json=lambda request, context: {
            "pots": [{"id": "pot_id", "balance": pot.balance, "deleted": False}]
        },
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance", json=card.respond
    )
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": monzo_balance}
    )
    requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json=pot.deposit)
    requests_mock.put("https://api.monzo.com/pots/pot_id/withdraw", json=pot.withdraw)
    return pot, card


def _set_fields(account_type, **fields):
    record = AccountModel.query.filter_by(type=account_type).one()
    for field, value in fields.items():
        setattr(record, field, value)
    db.session.commit()


def _account(account_type):
    return AccountModel.query.filter_by(type=account_type).one_or_none()


def _save_setting(key, value):
    SqlAlchemySettingRepository(db).save(Setting(key, value))


def _setting(key):
    return SqlAlchemySettingRepository(db).get(key)


def _notification_titles(requests_mock):
    return [
        parse_qs(req.text)["params[title]"][0]
        for req in requests_mock.request_history
        if req.method == "POST" and req.url == "https://api.monzo.com/feed"
    ]


def _pot_requests(requests_mock):
    return [req for req in requests_mock.request_history if "/pots" in req.url]


# ---------------------------------------------------------------------------
# Section 1: Monzo connection
# ---------------------------------------------------------------------------


def test_expiring_monzo_token_is_refreshed_and_persisted(mocker, test_client, requests_mock, seed_data):
    # The Monzo token is about to expire, so it is refreshed before the sync and the
    # new tokens are saved; the sync then carries on as normal.
    mocker.patch("app.core.scheduler")
    _set_fields("Monzo", token_expiry=int(time()))
    _set_fields(AMEX, prev_balance=1000)
    requests_mock.post(
        MONZO_TOKEN_URL,
        json={"access_token": "new_monzo_access", "refresh_token": "new_monzo_refresh", "expires_in": 3600},
    )
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)

    sync_balance()

    monzo = _account("Monzo")
    assert monzo.access_token == "new_monzo_access"
    assert monzo.refresh_token == "new_monzo_refresh"
    assert monzo.token_expiry > int(time()) + 3000
    ping = next(req for req in requests_mock.request_history if req.url.endswith("/ping/whoami"))
    assert ping.headers["Authorization"] == "Bearer new_monzo_access"
    assert pot.deposits == [] and pot.withdrawals == []


def test_monzo_refresh_auth_failure_deletes_connection_and_aborts(mocker, test_client, requests_mock, seed_data):
    # Monzo rejects the refresh token: the Monzo connection is removed and no pot is
    # touched, even though the card is well above the pot.
    mocker.patch("app.core.scheduler")
    _set_fields("Monzo", token_expiry=int(time()))
    requests_mock.post(MONZO_TOKEN_URL, json={"error": "invalid_grant"})
    _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account("Monzo") is None
    assert _account(AMEX) is not None
    assert _pot_requests(requests_mock) == []
    assert _notification_titles(requests_mock) == []


def test_sync_exits_without_touching_pots_when_monzo_not_connected(mocker, test_client, requests_mock, seed_data):
    # No Monzo connection is configured: the credit card connection is kept but the
    # sync stops before any pot is read or moved.
    mocker.patch("app.core.scheduler")
    AccountModel.query.filter_by(type="Monzo").delete()
    db.session.commit()
    _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account(AMEX) is not None
    assert _pot_requests(requests_mock) == []


# ---------------------------------------------------------------------------
# Section 2: credit card connections
# ---------------------------------------------------------------------------


def test_expiring_card_token_is_refreshed_and_used_for_balance_calls(mocker, test_client, requests_mock, seed_data):
    # The card token is about to expire: it is refreshed, persisted, and the new
    # token is what the balance calls are made with.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, token_expiry=int(time()), prev_balance=1000)
    requests_mock.post(
        TRUELAYER_TOKEN_URL,
        json={"access_token": "new_card_access", "refresh_token": "new_card_refresh", "expires_in": 3600},
    )
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)

    sync_balance()

    amex = _account(AMEX)
    assert amex.access_token == "new_card_access"
    assert amex.refresh_token == "new_card_refresh"
    balance_calls = [req for req in requests_mock.request_history if req.url.endswith("/cards/card_id/balance")]
    assert balance_calls
    assert all(req.headers["Authorization"] == "Bearer new_card_access" for req in balance_calls)


@pytest.mark.parametrize(
    "refresh_response",
    [
        {"error": "provider_error"},
        {"error": "temporarily_unavailable", "error_description": "The provider is currently unavailable"},
    ],
    ids=["provider_error", "currently_unavailable"],
)
def test_card_provider_outage_keeps_connection_and_does_not_notify(
    mocker, test_client, requests_mock, seed_data, refresh_response
):
    # A refresh failure caused by the card provider being down is transient: the
    # connection must be kept for a later retry and the user is not told to reconnect.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, token_expiry=int(time()), prev_balance=1000)
    requests_mock.post(TRUELAYER_TOKEN_URL, json=refresh_response)
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)

    sync_balance()

    amex = _account(AMEX)
    assert amex is not None
    assert amex.access_token == "access_token"
    assert _notification_titles(requests_mock) == []


def test_card_auth_failure_notifies_user_and_deletes_connection(mocker, test_client, requests_mock, seed_data):
    # The card's refresh token has been revoked: the user is notified through Monzo
    # to reconnect and the dead connection is removed.
    mocker.patch("app.core.scheduler")
    _save_setting("enable_sync", "False")
    _set_fields(AMEX, token_expiry=int(time()))
    requests_mock.post(TRUELAYER_TOKEN_URL, json={"error": "invalid_grant"})
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account(AMEX) is None
    assert _notification_titles(requests_mock) == [f"{AMEX} Pot Sync Access Expired"]
    assert pot.deposits == [] and pot.withdrawals == []


def test_card_auth_failure_without_monzo_deletes_connection_silently(mocker, test_client, requests_mock, seed_data):
    # With no Monzo connection there is nowhere to send a notification; the revoked
    # card connection is still removed and the sync exits.
    mocker.patch("app.core.scheduler")
    AccountModel.query.filter_by(type="Monzo").delete()
    db.session.commit()
    _set_fields(AMEX, token_expiry=int(time()))
    requests_mock.post(TRUELAYER_TOKEN_URL, json={"error": "invalid_grant"})
    _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account(AMEX) is None
    assert _notification_titles(requests_mock) == []
    assert _pot_requests(requests_mock) == []


def test_sync_exits_when_no_credit_cards_connected(mocker, test_client, requests_mock, seed_data):
    # Monzo is healthy but there are no cards to sync against: nothing is read from
    # or moved between pots.
    mocker.patch("app.core.scheduler")
    AccountModel.query.filter_by(type=AMEX).delete()
    db.session.commit()
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=500)

    sync_balance()

    assert any(req.url.endswith("/ping/whoami") for req in requests_mock.request_history)
    assert _pot_requests(requests_mock) == []


# ---------------------------------------------------------------------------
# Section 3: pot designation and the sync switch
# ---------------------------------------------------------------------------


def test_sync_exits_when_card_has_no_designated_pot(mocker, test_client, requests_mock, seed_data):
    # The card has no pot selected: the sync stops without moving money or recording
    # a baseline or cooldown.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, pot_id=None)
    _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    amex = _account(AMEX)
    assert amex.prev_balance == 0
    assert amex.cooldown_until is None
    assert not any(req.method == "PUT" for req in requests_mock.request_history)


def test_disabled_sync_moves_no_money(mocker, test_client, requests_mock, seed_data):
    # Sync is switched off: even with the card £500 above the pot nothing is deposited
    # and the card baseline is left alone.
    mocker.patch("app.core.scheduler")
    _save_setting("enable_sync", "False")
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert pot.deposits == [] and pot.withdrawals == []
    amex = _account(AMEX)
    assert amex.prev_balance == 0
    assert amex.cooldown_until is None


# ---------------------------------------------------------------------------
# Section 5: cooldown checks
# ---------------------------------------------------------------------------


def test_active_cooldown_cleared_once_pot_restored_to_reference(mocker, test_client, requests_mock, seed_data):
    # The user put the money back in the pot while the cooldown was running: the pot
    # is back at the card balance the cooldown was opened against, so it ends early
    # with nothing to move.
    mocker.patch("app.core.scheduler")
    _set_fields(
        AMEX,
        prev_balance=196327,
        cooldown_until=int(time()) + 3 * 3600,
        cooldown_ref_card_balance=196327,
    )
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=196327, card_balance=1963.27)

    sync_balance()

    amex = _account(AMEX)
    assert amex.cooldown_until is None
    assert amex.cooldown_ref_card_balance is None
    assert amex.prev_balance == 196327
    assert pot.deposits == [] and pot.withdrawals == []


def test_active_cooldown_cleared_and_pot_emptied_when_card_paid_off(mocker, test_client, requests_mock, seed_data):
    # The card payment cleared in full during the cooldown: the cooldown ends and the
    # pot, which no longer needs to cover anything, is emptied back to the account.
    mocker.patch("app.core.scheduler")
    _set_fields(
        AMEX,
        prev_balance=196327,
        cooldown_until=int(time()) + 3 * 3600,
        cooldown_ref_card_balance=196327,
    )
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=0)

    sync_balance()

    amex = _account(AMEX)
    assert amex.cooldown_until is None
    assert amex.cooldown_ref_card_balance is None
    assert amex.prev_balance == 0
    assert pot.deposits == []
    assert pot.withdrawals == [193400]
    assert pot.balance == 0


def test_expired_cooldown_with_insufficient_funds_disables_sync_and_notifies(
    mocker, test_client, requests_mock, seed_data
):
    # The cooldown expired with the pot £29.27 short, but the current account only
    # holds £1: nothing is deposited, sync is switched off and the user is told how
    # much to top up.
    mocker.patch("app.core.scheduler")
    _set_fields(
        AMEX,
        prev_balance=196327,
        cooldown_until=int(time()) - 60,
        cooldown_ref_card_balance=196327,
    )
    pot, _ = _mock_sync_endpoints(
        requests_mock, pot_balance=193400, card_balance=1963.27, monzo_balance=100
    )

    sync_balance()

    assert pot.deposits == [] and pot.withdrawals == []
    assert _setting("enable_sync") is False
    assert _notification_titles(requests_mock) == ["Lacking £28.27 - Insufficient Funds, Sync Disabled"]


def test_expired_cooldown_retained_when_pot_drops_during_validation(mocker, test_client, requests_mock, seed_data):
    # At expiry the pot first reads level with the card, but has dropped by £1 on the
    # confirming re-read. The expired cooldown is not cleared; the adjustment step then
    # treats the unexplained drop as a new pot withdrawal and opens a fresh cooldown
    # instead of refilling the pot.
    mocker.patch("app.core.scheduler")
    expired = int(time()) - 60
    _set_fields(AMEX, prev_balance=100000, cooldown_until=expired, cooldown_ref_card_balance=100000)
    pot_holder = {}

    def raid_pot_on_expiry_check(request_number):
        # 1st balance request is the pot differential step, 2nd is the expiry check,
        # which sits between the two pot reads being compared.
        if request_number == 2:
            pot_holder["pot"].balance -= 100

    pot, _ = _mock_sync_endpoints(
        requests_mock, pot_balance=100000, card_balance=1000.00, on_card_request=raid_pot_on_expiry_check
    )
    pot_holder["pot"] = pot

    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == [] and pot.withdrawals == []
    assert pot.balance == 99900
    assert amex.cooldown_until > int(time()) + 3 * 3600 - 60
    assert amex.cooldown_ref_card_balance == 100000
    assert amex.prev_balance == 100000


def test_cooldown_started_concurrently_is_not_replaced(mocker, test_client, requests_mock, seed_data):
    # Same drop as above, but another sync run persists its own cooldown while this
    # one is mid-adjustment. The persisted cooldown is re-checked and kept rather than
    # being overwritten with a new one.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=100000, cooldown_until=int(time()) - 60, cooldown_ref_card_balance=100000)
    concurrent_cooldown = int(time()) + 7200
    pot_holder = {}

    def interleave(request_number):
        if request_number == 2:
            pot_holder["pot"].balance -= 100
        if request_number == 3:
            # 3rd balance request is the start of the adjustment step.
            _set_fields(AMEX, cooldown_until=concurrent_cooldown, cooldown_ref_card_balance=100000)

    pot, _ = _mock_sync_endpoints(
        requests_mock, pot_balance=100000, card_balance=1000.00, on_card_request=interleave
    )
    pot_holder["pot"] = pot

    sync_balance()

    amex = _account(AMEX)
    assert amex.cooldown_until == concurrent_cooldown
    assert amex.cooldown_ref_card_balance == 100000
    assert amex.prev_balance == 100000
    assert pot.deposits == [] and pot.withdrawals == []


# ---------------------------------------------------------------------------
# Section 6: override branch
# ---------------------------------------------------------------------------


def test_override_deposits_new_spending_during_cooldown(mocker, test_client, requests_mock, seed_data):
    # With "override cooldown spending" on, £50 of new card spending during an active
    # cooldown is deposited straight away. The cooldown and its reference stay in
    # place so the earlier shortfall is still held back.
    mocker.patch("app.core.scheduler")
    _save_setting("override_cooldown_spending", "True")
    cooldown_until = int(time()) + 3 * 3600
    _set_fields(AMEX, prev_balance=100000, cooldown_until=cooldown_until, cooldown_ref_card_balance=100000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=90000, card_balance=1050.00)

    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == [5000]
    assert pot.withdrawals == []
    assert amex.prev_balance == 105000
    assert amex.cooldown_until == cooldown_until
    assert amex.cooldown_ref_card_balance == 100000


def test_override_off_holds_new_spending_during_cooldown(mocker, test_client, requests_mock, seed_data):
    # Counterpart to the above with the override explicitly switched off: the new
    # spending is not deposited until the cooldown ends.
    mocker.patch("app.core.scheduler")
    _save_setting("override_cooldown_spending", "False")
    cooldown_until = int(time()) + 3 * 3600
    _set_fields(AMEX, prev_balance=100000, cooldown_until=cooldown_until, cooldown_ref_card_balance=100000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=90000, card_balance=1050.00)

    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == [] and pot.withdrawals == []
    assert amex.prev_balance == 100000
    assert amex.cooldown_until == cooldown_until


def test_override_withdraws_when_card_payment_lands_mid_run(mocker, test_client, requests_mock, seed_data):
    # Override is on and a cooldown is holding. The card payment lands between the
    # cooldown check and the adjustment, taking the card below the pot: the excess
    # is withdrawn from the pot and the card baseline follows the card down.
    mocker.patch("app.core.scheduler")
    _save_setting("override_cooldown_spending", "True")
    cooldown_until = int(time()) + 3 * 3600
    _set_fields(AMEX, prev_balance=100000, cooldown_until=cooldown_until, cooldown_ref_card_balance=100000)
    card_holder = {}

    def payment_lands(request_number):
        # 3rd balance request is the start of the adjustment step.
        if request_number == 3:
            card_holder["card"].balance = 500.00

    pot, card = _mock_sync_endpoints(
        requests_mock, pot_balance=90000, card_balance=1000.00, on_card_request=payment_lands
    )
    card_holder["card"] = card

    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == []
    assert pot.withdrawals == [40000]
    assert pot.balance == 50000
    assert amex.prev_balance == 50000


# ---------------------------------------------------------------------------
# Section 6: standard adjustment
# ---------------------------------------------------------------------------


def test_new_spending_with_insufficient_funds_disables_sync_and_notifies(
    mocker, test_client, requests_mock, seed_data
):
    # £1000 of new spending but only £1 in the current account: no deposit is
    # attempted, sync is switched off and the user is told the shortfall.
    mocker.patch("app.core.scheduler")
    pot, _ = _mock_sync_endpoints(
        requests_mock, pot_balance=1000, card_balance=1000.00, monzo_balance=100
    )

    sync_balance()

    assert pot.deposits == [] and pot.withdrawals == []
    assert _setting("enable_sync") is False
    assert _notification_titles(requests_mock) == ["Lacking £989.00 - Insufficient Funds, Sync Disabled"]


def test_card_paid_down_to_pot_level_updates_baseline_only(mocker, test_client, requests_mock, seed_data):
    # The card dropped from £50 to £30 and the pot already holds £30: no money needs
    # moving, but the card baseline is brought down to the new balance.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=5000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=3000, card_balance=30.00)

    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == [] and pot.withdrawals == []
    assert amex.prev_balance == 3000
    assert amex.cooldown_until is None


def test_invalid_cooldown_hours_setting_falls_back_to_three_hours(mocker, test_client, requests_mock, seed_data):
    # The cooldown length setting holds garbage: a pot drop still opens a cooldown,
    # using the 3 hour default.
    mocker.patch("app.core.scheduler")
    _save_setting("deposit_cooldown_hours", "not-a-number")
    _set_fields(AMEX, prev_balance=196327)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    before = int(time())
    sync_balance()
    after = int(time())

    amex = _account(AMEX)
    assert before + 3 * 3600 <= amex.cooldown_until <= after + 3 * 3600
    assert amex.cooldown_ref_card_balance == 196327
    assert pot.deposits == [] and pot.withdrawals == []


def test_configured_cooldown_hours_are_used(mocker, test_client, requests_mock, seed_data):
    # A valid cooldown length setting is honoured.
    mocker.patch("app.core.scheduler")
    _save_setting("deposit_cooldown_hours", "5")
    _set_fields(AMEX, prev_balance=196327)
    _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    before = int(time())
    sync_balance()
    after = int(time())

    amex = _account(AMEX)
    assert before + 5 * 3600 <= amex.cooldown_until <= after + 5 * 3600


def test_database_error_verifying_cooldown_is_rolled_back_and_sync_completes(
    mocker, test_client, requests_mock, seed_data, caplog
):
    # Reading the cooldown back after saving it fails with a database error: the
    # error is logged, the session rolled back, the already-saved cooldown survives
    # and the run still finishes.
    caplog.set_level(logging.INFO)
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=196327)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    real_save = core.account_repository.save
    real_get = core.account_repository.get
    state = {"armed": False}

    def save(account):
        real_save(account)
        if account.type == AMEX and account.cooldown_until is not None:
            state["armed"] = True

    def get(account_type):
        if state["armed"]:
            state["armed"] = False
            raise SQLAlchemyError("database is locked")
        return real_get(account_type)

    mocker.patch.object(core.account_repository, "save", side_effect=save)
    mocker.patch.object(core.account_repository, "get", side_effect=get)
    rollback = mocker.spy(db.session, "rollback")

    sync_balance()

    assert rollback.called
    assert "Error committing cooldown to database: database is locked" in caplog.text
    assert "All credit accounts processed." in caplog.text
    amex = _account(AMEX)
    assert amex.cooldown_until is not None
    assert amex.cooldown_ref_card_balance == 196327
    assert pot.deposits == [] and pot.withdrawals == []


# ---------------------------------------------------------------------------
# Regression tests for bugs found while covering the sync loop
# ---------------------------------------------------------------------------


def test_revoked_card_is_dropped_from_the_run_and_other_cards_still_sync(
    mocker, test_client, requests_mock, seed_data
):
    # Amex's refresh token is revoked while a second card is healthy. The Amex
    # connection is deleted and the run carries on with the other card; it used to
    # crash looking up the deleted connection, so no card was synced at all.
    from app.domain.accounts import TrueLayerAccount
    from app.models.account_repository import SqlAlchemyAccountRepository

    mocker.patch("app.core.scheduler")
    SqlAlchemyAccountRepository(db).save(
        TrueLayerAccount("Barclaycard", "access_token", "refresh_token", time() + 10000, "pot_id")
    )
    _set_fields(AMEX, token_expiry=int(time()))
    requests_mock.post(TRUELAYER_TOKEN_URL, json={"error": "invalid_grant"})
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account(AMEX) is None
    assert _notification_titles(requests_mock) == [f"{AMEX} Pot Sync Access Expired"]
    assert pot.deposits == [50000]
    assert _account("Barclaycard").prev_balance == 50000


def test_unavailable_provider_is_skipped_for_the_run(mocker, test_client, requests_mock, seed_data):
    # The provider is down: the connection is kept for the next run, and this run
    # moves no money for it rather than failing part way through.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, token_expiry=int(time()), prev_balance=0)
    requests_mock.post(TRUELAYER_TOKEN_URL, json={"error": "provider_error"})
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=500)

    sync_balance()

    assert _account(AMEX) is not None
    assert pot.deposits == [] and pot.withdrawals == []


def test_no_zero_deposit_when_pot_already_covers_new_spending(mocker, test_client, requests_mock, seed_data):
    # The card went up from £0 to £10 but the pot already holds £10: only the
    # baseline moves. A £0 deposit used to be sent to Monzo.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=0)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10.00)

    sync_balance()

    assert not any(req.url.endswith("/deposit") for req in requests_mock.request_history)
    assert pot.deposits == [] and pot.withdrawals == []
    assert _account(AMEX).prev_balance == 1000


def test_sync_disabled_mid_run_does_not_start_a_new_cooldown(mocker, test_client, requests_mock, seed_data):
    # An expired cooldown can't be settled for lack of funds, which switches sync off.
    # Later in the same run the "pot below card, no new spending" step must respect
    # that and not open a fresh cooldown. The check compared the setting with the
    # string "False", but it is read back as a boolean, so it never matched.
    mocker.patch("app.core.scheduler")
    expired = int(time()) - 60
    _set_fields(AMEX, prev_balance=100000, cooldown_until=expired, cooldown_ref_card_balance=100000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=90000, card_balance=1000.00, monzo_balance=100)

    sync_balance()

    amex = _account(AMEX)
    assert _setting("enable_sync") is False
    assert pot.deposits == []
    assert amex.cooldown_until == expired


@pytest.mark.parametrize("stored", ["1", "True"])
def test_override_setting_default_is_read_as_on(mocker, test_client, requests_mock, seed_data, stored):
    # A fresh install stores the default as "1"; it used to be read as off, holding
    # back new spending during a cooldown until the settings page was saved.
    mocker.patch("app.core.scheduler")
    _save_setting("override_cooldown_spending", stored)
    cooldown_until = int(time()) + 3 * 3600
    _set_fields(AMEX, prev_balance=100000, cooldown_until=cooldown_until, cooldown_ref_card_balance=100000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=90000, card_balance=1050.00)

    sync_balance()

    assert pot.deposits == [5000]


def test_cooldown_cleared_during_a_run_is_not_restored(mocker, test_client, requests_mock, seed_data):
    # The user presses "Clear Cooldown" while a sync is running (simulated on the
    # first card balance request, before the run refreshes its account data). The
    # clear resets the baseline to the pot, so the pot is topped up straight away.
    # The run used to write its stale copy of the cooldown back to the database.
    mocker.patch("app.core.scheduler")
    _set_fields(
        AMEX,
        prev_balance=100000,
        cooldown_until=int(time()) + 3 * 3600,
        cooldown_ref_card_balance=100000,
    )

    def clear_cooldown(request_number):
        if request_number == 1:
            _set_fields(AMEX, cooldown_until=None, cooldown_ref_card_balance=None, prev_balance=90000)

    pot, _ = _mock_sync_endpoints(
        requests_mock, pot_balance=90000, card_balance=1000.00, on_card_request=clear_cooldown
    )

    sync_balance()

    amex = _account(AMEX)
    assert amex.cooldown_until is None
    assert pot.deposits == [10000]


def test_unfunded_spending_is_deposited_once_sync_is_re_enabled(mocker, test_client, requests_mock, seed_data):
    # £100 of new spending can't be covered, so sync is switched off. The card
    # baseline must stay where it was: once the user tops up and re-enables sync the
    # spending is deposited straight away. It used to be absorbed into the baseline,
    # so the next run read it as a pot drop and held it back behind a cooldown.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=90000)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=90000, card_balance=1000.00, monzo_balance=100)

    sync_balance()

    assert pot.deposits == []
    assert _account(AMEX).prev_balance == 90000

    requests_mock.get("https://api.monzo.com/balance?account_id=acc_id", json={"balance": 1000000})
    _save_setting("enable_sync", "True")
    sync_balance()

    amex = _account(AMEX)
    assert pot.deposits == [10000]
    assert amex.cooldown_until is None


@pytest.mark.parametrize(
    "stored, expected_deposit",
    [
        (None, 5000),      # connection made before the option existed: on
        (True, 5000),
        (False, 10000),    # pending refund not counted for this connection
    ],
)
def test_include_pending_credits_is_applied_per_connection(
    mocker, test_client, requests_mock, seed_data, stored, expected_deposit
):
    # An Amex card owes £100 with a £50 pending refund. Counting the refund, £50 is
    # set aside; with the option off for this connection, the full £100.
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=0, include_pending_credits=stored)
    pot, _ = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=100.00)
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id", "provider": {"display_name": "AMEX"}}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/transactions/pending",
        json={"results": [{"amount": -50.00}]},
    )

    sync_balance()

    assert pot.deposits == [expected_deposit]
