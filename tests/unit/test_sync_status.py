"""The dashboard snapshot kept in the settings table (``app.sync_status``)."""

import json
import logging

from app import security, sync_status
from app.domain.settings import Setting
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository


def test_load_without_a_snapshot(test_client):
    assert sync_status.load() == {"checked_at": None, "accounts": []}


def test_save_and_load_round_trip(test_client):
    accounts = [
        {"type": "American Express", "card_balance": 1234, "pot_balance": 1000, "pot_id": "pot_1"},
        {"type": "Barclaycard", "card_balance": None, "pot_balance": None, "pot_id": None},
    ]

    sync_status.save(accounts, 1_800_000_000.5)

    assert sync_status.load() == {"checked_at": 1_800_000_000.5, "accounts": accounts}
    stored = SqlAlchemySettingRepository(db).get(sync_status.KEY)
    assert json.loads(stored) == {"checked_at": 1_800_000_000.5, "accounts": accounts}


def test_save_replaces_the_previous_snapshot(test_client):
    sync_status.save([{"type": "A"}], 1.0)
    sync_status.save([{"type": "B"}], 2.0)

    assert sync_status.load() == {"checked_at": 2.0, "accounts": [{"type": "B"}]}


def test_load_ignores_a_corrupt_snapshot(test_client):
    SqlAlchemySettingRepository(db).save(Setting(sync_status.KEY, "{not json"))

    assert sync_status.load() == {"checked_at": None, "accounts": []}


def test_load_fills_missing_fields(test_client):
    SqlAlchemySettingRepository(db).save(Setting(sync_status.KEY, json.dumps({"checked_at": 5})))

    assert sync_status.load() == {"checked_at": 5, "accounts": []}


def test_load_with_an_empty_setting(test_client):
    SqlAlchemySettingRepository(db).save(Setting(sync_status.KEY, ""))

    assert sync_status.load() == {"checked_at": None, "accounts": []}


def test_load_with_a_non_string_value(mocker):
    # json.loads raises TypeError for values that aren't text.
    mocker.patch.object(security, "get_setting", return_value=12345)

    assert sync_status.load() == {"checked_at": None, "accounts": []}


def test_save_failure_is_logged_not_raised(mocker, caplog):
    mocker.patch.object(security, "set_setting", side_effect=RuntimeError("database is locked"))

    with caplog.at_level(logging.ERROR, logger="sync_status"):
        sync_status.save([{"type": "A"}], 1.0)

    assert "Failed to save the dashboard status" in caplog.text
    assert "database is locked" in caplog.text
