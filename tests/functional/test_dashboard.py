"""The home page dashboard and setup checklist, POST /sync-now and the ``pounds`` and
``relative_time`` template filters."""

import datetime
import html
import re
from time import time
from urllib.parse import urlparse

import pytest
from apscheduler.jobstores.base import JobLookupError

from app import sync_status
from app.domain.auth_providers import AuthProviderType
from app.domain.settings import Setting
from app.extensions import db
from app.models.account import AccountModel
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.sync_run_repository import SqlAlchemySyncRunRepository
from app.web.home import pounds, relative_time

AMEX = AuthProviderType.AMEX.value


def _save_setting(key, value):
    SqlAlchemySettingRepository(db).save(Setting(key, value))


def _set_fields(account_type, **fields):
    record = AccountModel.query.filter_by(type=account_type).one()
    for field, value in fields.items():
        setattr(record, field, value)
    db.session.commit()


def _page(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    # Collapse whitespace so assertions don't depend on template indentation.
    return re.sub(r"\s+", " ", html.unescape(response.data.decode()))


def _snapshot(**overrides):
    entry = {
        "type": AMEX,
        "provider": AMEX,
        "icon": "amex.svg",
        "card_balance": 196327,
        "pot_id": "pot_id",
        "pot_name": "Credit Cards",
        "pot_balance": 196327,
        "cooldown_until": None,
        "consent_expires_at": None,
    }
    entry.update(overrides)
    return entry


@pytest.fixture
def configured(test_client, seed_data):
    """Client IDs saved, Monzo and a card connected and the card's pot chosen."""
    _save_setting("monzo_client_id", "monzo_id")
    _save_setting("truelayer_client_id", "truelayer_id")


# ---------------------------------------------------------------------------
# Setup checklist
# ---------------------------------------------------------------------------


def _step_done(page, label):
    """Whether the checklist marks the step with ``label`` as done."""
    match = re.search(r"<a href=\"[^\"]*\"[^>]*>(?:(?!</a>).)*?" + re.escape(label), page)
    assert match, f"step {label!r} not on the page"
    return "Done:" in match.group(0)


def test_fresh_install_shows_every_step_outstanding(test_client):
    page = _page(test_client)

    assert "Get set up" in page
    assert "Overview" not in page
    for label in (
        "Add your Monzo and TrueLayer client IDs and secrets",
        "Connect your Monzo account",
        "Connect a credit card",
        "Choose the pot each card syncs with",
    ):
        assert not _step_done(page, label)
    assert 'href="/settings/"' in page
    assert 'href="/accounts/add"' in page
    assert 'href="/pots/"' in page


def test_client_ids_step_needs_both_monzo_and_truelayer(test_client):
    _save_setting("monzo_client_id", "monzo_id")
    assert not _step_done(_page(test_client), "Add your Monzo and TrueLayer client IDs")

    _save_setting("truelayer_client_id", "truelayer_id")
    assert _step_done(_page(test_client), "Add your Monzo and TrueLayer client IDs")


def test_card_still_on_default_pot_keeps_setup_incomplete(test_client, seed_data):
    _save_setting("monzo_client_id", "monzo_id")
    _save_setting("truelayer_client_id", "truelayer_id")
    _set_fields(AMEX, pot_id="default_pot")

    page = _page(test_client)

    assert "Get set up" in page
    assert _step_done(page, "Connect your Monzo account")
    assert _step_done(page, "Connect a credit card")
    assert not _step_done(page, "Choose the pot each card syncs with")


def test_card_without_a_pot_keeps_setup_incomplete(test_client, seed_data):
    _save_setting("monzo_client_id", "monzo_id")
    _save_setting("truelayer_client_id", "truelayer_id")
    _set_fields(AMEX, pot_id=None)

    assert not _step_done(_page(test_client), "Choose the pot each card syncs with")


def test_monzo_missing_keeps_setup_incomplete(test_client, seed_data):
    _save_setting("monzo_client_id", "monzo_id")
    _save_setting("truelayer_client_id", "truelayer_id")
    AccountModel.query.filter_by(type="Monzo").delete()
    db.session.commit()

    page = _page(test_client)

    assert "Get set up" in page
    assert not _step_done(page, "Connect your Monzo account")
    assert _step_done(page, "Connect a credit card")
    assert _step_done(page, "Choose the pot each card syncs with")


def test_every_card_needs_a_pot(test_client, configured):
    db.session.add(AccountModel(type="Barclaycard", provider="Barclaycard", access_token="a",
                                refresh_token="r", pot_id="default_pot"))
    db.session.commit()

    assert not _step_done(_page(test_client), "Choose the pot each card syncs with")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_complete_setup_shows_dashboard_waiting_for_first_sync(test_client, configured):
    page = _page(test_client)

    assert "Overview" in page
    assert "Get set up" not in page
    assert "No sync has run yet" in page
    assert "Sync is off" not in page
    assert 'action="/sync-now"' in page
    assert AMEX in page
    # Nothing is known about the card until a sync has saved a snapshot.
    assert re.search(r"Card owes</dt> <dd[^>]*>–</dd>", page)
    assert re.search(r">Pot</dt> <dd[^>]*>–</dd>", page)
    assert "Waiting for the next sync" in page


def test_card_in_sync(test_client, configured):
    sync_status.save([_snapshot()], time())

    page = _page(test_client)

    assert "£1,963.27" in page
    assert "Credit Cards" in page
    assert "In sync" in page
    assert "Waiting for the next sync" not in page


def test_pot_short_of_card_balance(test_client, configured):
    sync_status.save([_snapshot(card_balance=196327, pot_balance=193400)], time())

    page = _page(test_client)

    assert "Pot short by £29.27" in page
    assert "£1,934.00" in page


def test_pot_over_card_balance(test_client, configured):
    sync_status.save([_snapshot(card_balance=1000, pot_balance=1550)], time())

    assert "Pot over by £5.50" in _page(test_client)


def test_snapshot_for_a_different_pot_is_not_shown(test_client, configured):
    # The card was moved to another pot since the last sync: its old pot's balance
    # and name are not shown against the new pot.
    sync_status.save([_snapshot(pot_id="old_pot", pot_name="Old Pot", pot_balance=999999)], time())

    page = _page(test_client)

    assert "£1,963.27" in page  # the card balance is still valid
    assert "Old Pot" not in page
    assert "£9,999.99" not in page
    assert "Waiting for the next sync" in page


def test_card_balance_unknown_shows_waiting(test_client, configured):
    sync_status.save([_snapshot(card_balance=None)], time())

    page = _page(test_client)

    assert "Waiting for the next sync" in page
    assert "In sync" not in page


def test_snapshot_for_another_card_is_ignored(test_client, configured):
    sync_status.save([_snapshot(type="Barclaycard", card_balance=5, pot_balance=5)], time())

    page = _page(test_client)

    assert "Waiting for the next sync" in page
    assert "In sync" not in page


def test_active_cooldown_is_shown(test_client, configured):
    _set_fields(AMEX, cooldown_until=int(time()) + 2 * 3600 + 120)

    assert "Cooldown ends in 2 hours" in _page(test_client)


def test_expired_cooldown_is_not_shown(test_client, configured):
    _set_fields(AMEX, cooldown_until=int(time()) - 60)

    assert "Cooldown ends" not in _page(test_client)


def test_consent_expiring_soon_prompts_reconnect(test_client, configured):
    _set_fields(AMEX, consent_expires_at=int(time()) + 3 * 86400 + 600)

    page = _page(test_client)

    assert "Reconnect in 3 days" in page
    assert 'href="/accounts/"' in page


def test_expired_consent_says_reconnect_needed(test_client, configured):
    _set_fields(AMEX, consent_expires_at=int(time()) - 3600)

    page = _page(test_client)

    assert "Reconnect needed" in page
    assert "Reconnect in" not in page


def test_consent_far_from_expiry_shows_no_prompt(test_client, configured):
    _set_fields(AMEX, consent_expires_at=int(time()) + 15 * 86400)

    page = _page(test_client)

    assert "Reconnect in" not in page
    assert "Reconnect needed" not in page


def test_consent_just_inside_warning_window_prompts(test_client, configured):
    _set_fields(AMEX, consent_expires_at=int(time()) + 14 * 86400 - 600)

    assert "Reconnect in 13 days" in _page(test_client)


def test_sync_disabled_is_flagged(test_client, configured):
    _save_setting("enable_sync", "False")

    assert "Sync is off" in _page(test_client)


@pytest.mark.parametrize("stored", ["1", "true", "True"])
def test_sync_enabled_values(test_client, configured, stored):
    _save_setting("enable_sync", stored)

    assert "Sync is off" not in _page(test_client)


def test_latest_run_is_summarised(test_client, configured):
    now = time()
    SqlAlchemySyncRunRepository(db).record([[now, "INFO", "core", "All good"]], now - 300, now - 290)

    page = _page(test_client)

    assert "Last sync 4 minutes ago" in page
    assert "No sync has run yet" not in page
    assert ">Error<" not in page and ">Warning<" not in page
    assert "View logs" not in page


def test_latest_run_error_is_shown_with_link_to_logs(test_client, configured):
    now = time()
    SqlAlchemySyncRunRepository(db).record(
        [
            [now, "INFO", "core", "Starting"],
            [now, "ERROR", "core", "Monzo is down\nTraceback (most recent call last): ..."],
        ],
        now - 10,
        now - 5,
    )

    page = _page(test_client)

    assert ">Error</span>" in page
    assert "Monzo is down · " in page
    assert "Traceback" not in page
    assert 'href="/logs/"' in page
    assert "text-red-700" in page


def test_latest_run_warning_is_shown(test_client, configured):
    now = time()
    SqlAlchemySyncRunRepository(db).record(
        [[now, "WARNING", "core", "Reconnect American Express soon"]], now - 10, now - 5
    )

    page = _page(test_client)

    assert ">Warning</span>" in page
    assert "Reconnect American Express soon" in page
    assert "text-orange-700" in page


# ---------------------------------------------------------------------------
# POST /sync-now
# ---------------------------------------------------------------------------


def test_sync_now_runs_the_sync_job_immediately(test_client, mocker):
    scheduler = mocker.patch("app.web.home.scheduler")

    before = datetime.datetime.now(datetime.timezone.utc)
    response = test_client.post("/sync-now")
    after = datetime.datetime.now(datetime.timezone.utc)

    assert response.status_code == 302
    assert urlparse(response.location).path == "/"
    scheduler.modify_job.assert_called_once()
    args, kwargs = scheduler.modify_job.call_args
    assert args == ("sync_balance",)
    assert before <= kwargs["next_run_time"] <= after
    assert kwargs["next_run_time"].tzinfo is not None
    with test_client.session_transaction() as session:
        assert session["_flashes"] == [("message", "Sync started. Refresh in a few seconds to see the result.")]


@pytest.mark.parametrize(
    "error",
    [JobLookupError("sync_balance"), AttributeError("no scheduler"), RuntimeError("not running")],
)
def test_sync_now_failure_is_reported(test_client, mocker, caplog, error):
    scheduler = mocker.patch("app.web.home.scheduler")
    scheduler.modify_job.side_effect = error

    response = test_client.post("/sync-now")

    assert response.status_code == 302
    assert urlparse(response.location).path == "/"
    with test_client.session_transaction() as session:
        assert session["_flashes"] == [("error", "Couldn't start a sync right now")]
    assert "Could not start a sync" in caplog.text


def test_sync_now_rejects_get(test_client):
    assert test_client.get("/sync-now").status_code == 405


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pence", "expected"),
    [
        (None, "–"),
        (0, "£0.00"),
        (5, "£0.05"),
        (196327, "£1,963.27"),
        (-2927, "-£29.27"),
        (123456789, "£1,234,567.89"),
    ],
)
def test_pounds(pence, expected):
    assert pounds(pence) == expected


@pytest.fixture
def frozen_now(mocker):
    now = 1_800_000_000
    mocker.patch("app.web.home.time", return_value=now)
    return now


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (0, "just now"),
        (-5, "just now"),
        (5, "just now"),
        (-6, "a few seconds ago"),
        (30, "in a few seconds"),
        (-59, "a few seconds ago"),
        (-60, "1 minute ago"),
        (-61, "1 minute ago"),
        (-120, "2 minutes ago"),
        (90, "in 1 minute"),
        (-3599, "59 minutes ago"),
        (-3600, "1 hour ago"),
        (7200, "in 2 hours"),
        (-86399, "23 hours ago"),
        (-86400, "1 day ago"),
        (3 * 86400 + 5, "in 3 days"),
        (-10 * 86400, "10 days ago"),
    ],
)
def test_relative_time(frozen_now, offset, expected):
    assert relative_time(frozen_now + offset) == expected


@pytest.mark.parametrize("timestamp", [None, 0])
def test_relative_time_never(timestamp):
    assert relative_time(timestamp) == "never"


def test_relative_time_accepts_float_timestamps(frozen_now):
    assert relative_time(frozen_now - 300.7) == "5 minutes ago"


def test_filters_are_registered_for_templates(test_client):
    env = test_client.application.jinja_env
    assert env.filters["pounds"] is pounds
    assert env.filters["relative_time"] is relative_time
