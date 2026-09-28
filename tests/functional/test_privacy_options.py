"""Hide amounts on the home page, and switching log history off."""

import logging
from time import time

import pytest

from app import security, sync_status
from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.sync_run import SyncRunModel
from app.models.sync_run_repository import SqlAlchemySyncRunRepository
from app.utils.sync_log import record_sync_run


@pytest.fixture
def configured(test_client):
    repository = SqlAlchemyAccountRepository(db)
    repository.save(MonzoAccount("a", "r", int(time()) + 1000, "pot_1"))
    repository.save(TrueLayerAccount("American Express", "a", "r", int(time()) + 1000, "pot_1", provider_type="American Express"))
    security.set_setting("monzo_client_id", "m")
    security.set_setting("truelayer_client_id", "t")
    sync_status.save([{"type": "American Express", "card_balance": 12345, "pot_id": "pot_1", "pot_name": "Cards", "pot_balance": 12345}], time())
    return test_client


def _save_settings(client, **checked):
    data = {key: "on" for key, on in checked.items() if on}
    return client.post("/settings/", data=data, follow_redirects=True)


def test_amounts_show_by_default(configured):
    page = configured.get("/").data.decode()
    assert 'id="overview" class="group w-full max-w-screen-lg "' in page
    assert "£123.45" in page
    assert 'aria-label="Hide amounts"' in page


def test_hide_amounts_setting_masks_the_dashboard(configured):
    _save_settings(configured, hide_balances=True, log_history_enabled=True, enable_sync=True)

    page = configured.get("/").data.decode()
    assert security.hide_balances() is True
    assert "amounts-hidden" in page
    assert "£•••••" in page
    assert 'aria-label="Show amounts"' in page


def test_hide_amounts_also_hides_the_problem_text(configured):
    sync_status.save_last_run([[time(), "ERROR", "core", "Insufficient funds; required £29.27"]], time() - 5, time())
    _save_settings(configured, hide_balances=True, log_history_enabled=True)

    page = configured.get("/").data.decode()
    assert "An error was logged (hidden)" in page


def test_settings_page_shows_both_options(configured):
    page = configured.get("/settings/").data.decode()
    assert "Hide Amounts on the Home Page" in page
    assert 'name="log_history_enabled" class="sr-only peer"  checked' in page  # on by default
    assert 'name="hide_balances" class="sr-only peer"  checked' not in page


def test_turning_log_history_off_clears_it_and_stops_recording(configured, caplog):
    caplog.set_level(logging.INFO)
    repository = SqlAlchemySyncRunRepository(db)
    repository.record([[time(), "INFO", "core", "Card is £10.00"]], time())
    assert db.session.query(SyncRunModel).count() == 1

    _save_settings(configured, enable_sync=True)  # log_history_enabled unchecked

    assert security.log_history_enabled() is False
    assert db.session.query(SyncRunModel).count() == 0

    with record_sync_run(repository):
        logging.getLogger("core").warning("Card is £20.00")

    assert db.session.query(SyncRunModel).count() == 0
    # The dashboard and /health still know a sync ran.
    last = sync_status.last_run()
    assert last["level"] == "WARNING"
    assert last["problem"] == "Card is £20.00"
    assert configured.get("/health").get_json()["status"] == "ok"


def test_logs_page_and_menu_when_history_is_off(configured):
    _save_settings(configured, enable_sync=True)

    page = configured.get("/logs/").data.decode()
    assert "Log history is off" in page
    home = configured.get("/").data.decode()
    assert 'href="/logs/"' not in home


def test_turning_log_history_back_on_records_again(configured, caplog):
    caplog.set_level(logging.INFO)
    _save_settings(configured, enable_sync=True)
    _save_settings(configured, enable_sync=True, log_history_enabled=True)

    with record_sync_run(SqlAlchemySyncRunRepository(db)):
        logging.getLogger("core").info("Card is £30.00")

    assert db.session.query(SyncRunModel).count() == 1
    assert 'href="/logs/"' in configured.get("/").data.decode()


def test_clear_log_history(configured):
    repository = SqlAlchemySyncRunRepository(db)
    repository.record([[time(), "INFO", "core", "one"]], time())
    repository.record([[time(), "INFO", "core", "two"]], time())

    page = configured.post("/logs/clear", follow_redirects=True).data.decode()

    assert "Log history cleared (2 entries)" in page
    assert db.session.query(SyncRunModel).count() == 0
    assert "Clear history" not in page  # nothing left to clear


def test_last_run_record_ignores_bad_data(test_client):
    security.set_setting(sync_status.LAST_RUN_KEY, "not json")
    assert sync_status.last_run() is None
    security.set_setting(sync_status.LAST_RUN_KEY, "[1, 2]")
    assert sync_status.last_run() is None


def test_last_run_save_failure_is_swallowed(test_client, mocker):
    mocker.patch("app.sync_status.security.set_setting", side_effect=RuntimeError("db locked"))
    sync_status.save_last_run([], time(), time())  # does not raise


@pytest.mark.parametrize("stored, expected", [(None, True), ("True", True), ("1", True), ("False", False), ("0", False)])
def test_log_history_setting_values(test_client, stored, expected):
    if stored is not None:
        security.set_setting("log_history_enabled", stored)
    else:
        from app.models.setting import SettingModel
        SettingModel.query.filter_by(key="log_history_enabled").delete()
        db.session.commit()
    assert security.log_history_enabled() is expected
