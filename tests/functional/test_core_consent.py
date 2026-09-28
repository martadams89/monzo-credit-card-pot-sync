"""Sync loop features in ``app.core``: consent expiry reminders, per-card cooldown
lengths and the dashboard snapshot saved at the end of a run."""

import datetime
import logging
from time import time
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest
import requests

from app import core, sync_status
from app.core import sync_balance
from app.domain.auth_providers import AuthProviderType
from app.domain.settings import Setting
from app.extensions import db
from app.models.account import AccountModel
from app.models.setting_repository import SqlAlchemySettingRepository

AMEX = AuthProviderType.AMEX.value
DAY = 86400


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


def _iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mock_sync_endpoints(requests_mock, *, pot_balance, card_balance, consent_expires_at=None, monzo_balance=1000000):
    """Wire up the Monzo and TrueLayer calls a sync run makes.

    ``pot_balance`` is in pence to match the Monzo API; ``card_balance`` is in pounds
    to match TrueLayer. ``consent_expires_at`` (epoch) is what /data/v1/me reports.
    """
    pot = _Pot(pot_balance)

    requests_mock.get("https://api.monzo.com/ping/whoami")
    if consent_expires_at is None:
        requests_mock.get("https://api.truelayer.com/data/v1/me")
    else:
        requests_mock.get(
            "https://api.truelayer.com/data/v1/me",
            json={"results": [{"consent_expires_at": _iso(consent_expires_at)}]},
        )
    requests_mock.get(
        "https://api.monzo.com/pots",
        json=lambda request, context: {
            "pots": [{"id": "pot_id", "name": "Credit Cards", "balance": pot.balance, "deleted": False}]
        },
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance",
        json={"results": [{"current": card_balance}]},
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
    return pot


def _set_fields(account_type, **fields):
    record = AccountModel.query.filter_by(type=account_type).one()
    for field, value in fields.items():
        setattr(record, field, value)
    db.session.commit()


def _account(account_type):
    db.session.expire_all()
    return AccountModel.query.filter_by(type=account_type).one_or_none()


def _save_setting(key, value):
    SqlAlchemySettingRepository(db).save(Setting(key, value))


def _notification_titles(requests_mock):
    return [
        parse_qs(req.text)["params[title]"][0]
        for req in requests_mock.request_history
        if req.method == "POST" and req.url == "https://api.monzo.com/feed"
    ]


def _date(epoch):
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc).strftime("%d %b")


@pytest.fixture
def steady(mocker, test_client, seed_data):
    """A card that matches its pot, so a run moves no money and sends no other notification."""
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=1000)


# ---------------------------------------------------------------------------
# Consent expiry
# ---------------------------------------------------------------------------


def test_consent_expiry_is_recorded_without_a_reminder_when_far_away(steady, requests_mock):
    expires = int(time()) + 30 * DAY
    pot = _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    amex = _account(AMEX)
    assert amex.consent_expires_at == expires
    assert amex.consent_reminder_sent_at is None
    assert _notification_titles(requests_mock) == []
    assert pot.deposits == [] and pot.withdrawals == []


def test_no_reminder_just_outside_the_reminder_window(steady, requests_mock):
    expires = int(time()) + 7 * DAY + 600
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    assert _notification_titles(requests_mock) == []
    assert _account(AMEX).consent_reminder_sent_at is None


def test_reminder_sent_when_consent_expires_within_a_week(steady, requests_mock, caplog):
    expires = int(time()) + 3 * DAY
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    before = int(time())
    with caplog.at_level(logging.WARNING, logger="core"):
        sync_balance()
    after = int(time())

    assert _notification_titles(requests_mock) == [f"Reconnect {AMEX} by {_date(expires)}"]
    feed = next(req for req in requests_mock.request_history if req.url == "https://api.monzo.com/feed")
    body = parse_qs(feed.text)
    assert "Reconnect" in body["params[body]"][0]
    assert body["account_id"] == ["acc_id"]
    amex = _account(AMEX)
    assert amex.consent_expires_at == expires
    assert before <= amex.consent_reminder_sent_at <= after
    assert f"{AMEX} connection expires on {_date(expires)}" in caplog.text


def test_reminder_sent_at_the_edge_of_the_window(steady, requests_mock):
    expires = int(time()) + 7 * DAY - 60
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    assert _notification_titles(requests_mock) == [f"Reconnect {AMEX} by {_date(expires)}"]


def test_expired_consent_uses_a_different_title(steady, requests_mock, caplog):
    expires = int(time()) - DAY
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    with caplog.at_level(logging.WARNING, logger="core"):
        sync_balance()

    assert _notification_titles(requests_mock) == [f"{AMEX} needs reconnecting"]
    assert f"{AMEX} connection expired on {_date(expires)}" in caplog.text
    assert _account(AMEX).consent_reminder_sent_at is not None


def test_reminder_not_repeated_within_a_day(steady, requests_mock):
    expires = int(time()) + 3 * DAY
    sent = int(time()) - 23 * 3600
    _set_fields(AMEX, consent_expires_at=expires, consent_reminder_sent_at=sent)
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    assert _notification_titles(requests_mock) == []
    assert _account(AMEX).consent_reminder_sent_at == sent


def test_reminder_repeated_after_a_day(steady, requests_mock):
    expires = int(time()) + 2 * DAY
    sent = int(time()) - 25 * 3600
    _set_fields(AMEX, consent_expires_at=expires, consent_reminder_sent_at=sent)
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    assert _notification_titles(requests_mock) == [f"Reconnect {AMEX} by {_date(expires)}"]
    assert _account(AMEX).consent_reminder_sent_at > sent


def test_two_runs_send_one_reminder(steady, requests_mock):
    expires = int(time()) + 3 * DAY
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()
    sync_balance()

    assert len(_notification_titles(requests_mock)) == 1


def test_failed_reminder_is_logged_and_the_sync_carries_on(steady, requests_mock, caplog):
    expires = int(time()) + 3 * DAY
    _set_fields(AMEX, prev_balance=1000)
    pot = _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=15, consent_expires_at=expires)
    requests_mock.post("https://api.monzo.com/feed", exc=requests.exceptions.ConnectionError("feed down"))

    sync_balance()

    assert f"Failed to send the reconnect reminder for {AMEX}: feed down" in caplog.text
    amex = _account(AMEX)
    # Not marked as sent, so the next run tries again.
    assert amex.consent_reminder_sent_at is None
    assert amex.consent_expires_at == expires
    # The card's new spending is still funded.
    assert pot.deposits == [500]


def test_unknown_expiry_leaves_the_stored_one(steady, requests_mock):
    _set_fields(AMEX, consent_expires_at=int(time()) + 60 * DAY)
    stored = _account(AMEX).consent_expires_at
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)  # /me has no body

    sync_balance()

    assert _account(AMEX).consent_expires_at == stored
    assert _notification_titles(requests_mock) == []


def test_unchanged_expiry_is_not_written_again(steady, requests_mock, mocker):
    expires = int(time()) + 30 * DAY
    _set_fields(AMEX, consent_expires_at=expires)
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)
    spy = mocker.spy(core.account_repository, "set_consent_expiry")

    sync_balance()

    spy.assert_not_called()


def test_changed_expiry_replaces_the_stored_one(steady, requests_mock):
    _set_fields(AMEX, consent_expires_at=int(time()) + 5 * DAY)
    expires = int(time()) + 90 * DAY
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    assert _account(AMEX).consent_expires_at == expires
    assert _notification_titles(requests_mock) == []


def test_expiry_recorded_but_no_reminder_without_monzo(mocker, test_client, requests_mock, seed_data):
    mocker.patch("app.core.scheduler")
    AccountModel.query.filter_by(type="Monzo").delete()
    db.session.commit()
    expires = int(time()) + DAY
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10, consent_expires_at=expires)

    sync_balance()

    amex = _account(AMEX)
    assert amex.consent_expires_at == expires
    assert amex.consent_reminder_sent_at is None
    assert _notification_titles(requests_mock) == []


def test_check_consent_expiry_ignores_none(mocker):
    set_expiry = mocker.patch.object(core.account_repository, "set_consent_expiry")
    monzo = mocker.Mock()
    card = SimpleNamespace(type=AMEX, consent_expires_at=5, consent_reminder_sent_at=None)

    core._check_consent_expiry(card, None, monzo)

    set_expiry.assert_not_called()
    monzo.send_notification.assert_not_called()
    assert card.consent_expires_at == 5


def test_check_consent_expiry_updates_the_in_memory_account(mocker):
    set_expiry = mocker.patch.object(core.account_repository, "set_consent_expiry")
    mark_sent = mocker.patch.object(core.account_repository, "mark_consent_reminder_sent")
    monzo = mocker.Mock()
    card = SimpleNamespace(type=AMEX, consent_expires_at=None, consent_reminder_sent_at=None)
    expires = int(time()) + DAY

    core._check_consent_expiry(card, expires, monzo)

    set_expiry.assert_called_once_with(AMEX, expires)
    assert card.consent_expires_at == expires
    monzo.send_notification.assert_called_once()
    mark_sent.assert_called_once()
    assert card.consent_reminder_sent_at == mark_sent.call_args.args[1]


def test_check_consent_expiry_marks_nothing_when_sending_raises(mocker, caplog):
    mocker.patch.object(core.account_repository, "set_consent_expiry")
    mark_sent = mocker.patch.object(core.account_repository, "mark_consent_reminder_sent")
    monzo = mocker.Mock()
    monzo.send_notification.side_effect = RuntimeError("no personal account")
    card = SimpleNamespace(type=AMEX, consent_expires_at=None, consent_reminder_sent_at=None)

    core._check_consent_expiry(card, int(time()) + DAY, monzo)

    mark_sent.assert_not_called()
    assert card.consent_reminder_sent_at is None
    assert "no personal account" in caplog.text


# ---------------------------------------------------------------------------
# Per-card cooldown length
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("card_hours", "global_setting", "expected_hours"),
    [
        (12, "5", 12),  # the card's own length wins
        (1, "5", 1),
        (720, "not-a-number", 720),
        (None, "5", 5),  # no per-card length: the global setting
        (None, "not-a-number", 3),  # and its fallback
    ],
)
def test_cooldown_length(mocker, test_client, requests_mock, seed_data, card_hours, global_setting, expected_hours):
    # The pot drops below the card without new spending, which opens a cooldown.
    mocker.patch("app.core.scheduler")
    _save_setting("deposit_cooldown_hours", global_setting)
    _set_fields(AMEX, prev_balance=196327, cooldown_hours=card_hours)
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    before = int(time())
    sync_balance()
    after = int(time())

    amex = _account(AMEX)
    assert before + expected_hours * 3600 <= amex.cooldown_until <= after + expected_hours * 3600
    assert amex.cooldown_ref_card_balance == 196327
    assert amex.cooldown_hours == card_hours
    assert pot.deposits == [] and pot.withdrawals == []


# ---------------------------------------------------------------------------
# Dashboard snapshot
# ---------------------------------------------------------------------------


def test_snapshot_saved_at_the_end_of_a_run(steady, requests_mock):
    expires = int(time()) + 30 * DAY
    _set_fields(AMEX, prev_balance=1000)
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=15, consent_expires_at=expires)

    before = time()
    sync_balance()
    after = time()

    status = sync_status.load()
    assert before <= status["checked_at"] <= after
    assert status["accounts"] == [
        {
            "type": AMEX,
            "provider": AMEX,
            "icon": "amex.svg",
            "card_balance": 1500,
            "pot_id": "pot_id",
            "pot_name": "Credit Cards",
            "pot_balance": 1500,  # after the run's deposit
            "cooldown_until": None,
            "consent_expires_at": expires,
        }
    ]


def test_snapshot_reflects_a_cooldown_started_in_the_run(mocker, test_client, requests_mock, seed_data):
    mocker.patch("app.core.scheduler")
    _set_fields(AMEX, prev_balance=196327)
    _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    sync_balance()

    (entry,) = sync_status.load()["accounts"]
    assert entry["cooldown_until"] == _account(AMEX).cooldown_until
    assert entry["card_balance"] == 196327
    assert entry["pot_balance"] == 193400


def test_no_snapshot_when_the_run_exits_early(mocker, test_client, requests_mock, seed_data):
    mocker.patch("app.core.scheduler")
    AccountModel.query.filter_by(type="Monzo").delete()
    db.session.commit()
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)

    sync_balance()

    assert sync_status.load() == {"checked_at": None, "accounts": []}


def test_dashboard_shows_the_snapshot_after_a_run(steady, requests_mock, test_client):
    _save_setting("monzo_client_id", "m")
    _save_setting("truelayer_client_id", "t")
    _mock_sync_endpoints(requests_mock, pot_balance=1000, card_balance=10)

    sync_balance()
    html = test_client.get("/").data.decode()

    assert "In sync" in html
    assert "Credit Cards" in html
    assert "£10.00" in html


class _FakeCard:
    def __init__(self, account_type, pot_id, balance):
        self.type = account_type
        self.provider_type = AMEX
        self.auth_provider = SimpleNamespace(icon_name="amex.svg")
        self.pot_id = pot_id
        self.cooldown_until = None
        self.consent_expires_at = None
        self._balance = balance

    def get_total_balance(self, force_refresh=False):
        assert force_refresh is False  # the snapshot reuses the run's figures
        if isinstance(self._balance, Exception):
            raise self._balance
        return self._balance


def test_snapshot_gathers_pots_across_accounts_and_tolerates_errors(test_client, mocker):
    monzo = mocker.Mock()
    pots_by_selection = {
        "personal": [{"id": "p1", "name": "Personal Pot", "balance": 100}],
        "joint": RuntimeError("no joint account"),
        "business": [
            {"id": "b1", "name": "Business Pot", "balance": 300},
            {"id": "p1", "name": "Duplicate", "balance": 999},
        ],
    }

    def get_pots(selection):
        result = pots_by_selection[selection]
        if isinstance(result, Exception):
            raise result
        return result

    monzo.get_pots.side_effect = get_pots
    cards = [
        _FakeCard("Card A", "p1", 150),
        _FakeCard("Card B", "b1", RuntimeError("card API down")),
        _FakeCard("Card C", "missing_pot", 0),
    ]

    core._snapshot_status(monzo, cards)

    assert [call.args[0] for call in monzo.get_pots.call_args_list] == ["personal", "joint", "business"]
    accounts = {a["type"]: a for a in sync_status.load()["accounts"]}
    assert list(accounts) == ["Card A", "Card B", "Card C"]
    assert accounts["Card A"]["pot_name"] == "Personal Pot"  # first pot found wins
    assert accounts["Card A"]["pot_balance"] == 100
    assert accounts["Card A"]["card_balance"] == 150
    assert accounts["Card B"]["pot_name"] == "Business Pot"
    assert accounts["Card B"]["pot_balance"] == 300
    assert accounts["Card B"]["card_balance"] is None
    assert accounts["Card C"]["pot_name"] is None
    assert accounts["Card C"]["pot_balance"] is None
    assert accounts["Card C"]["card_balance"] == 0


def test_snapshot_with_no_pots_anywhere(test_client, mocker):
    monzo = mocker.Mock()
    monzo.get_pots.side_effect = RuntimeError("Monzo down")

    core._snapshot_status(monzo, [_FakeCard("Card A", "p1", 150)])

    (entry,) = sync_status.load()["accounts"]
    assert entry["pot_name"] is None and entry["pot_balance"] is None
    assert entry["card_balance"] == 150
