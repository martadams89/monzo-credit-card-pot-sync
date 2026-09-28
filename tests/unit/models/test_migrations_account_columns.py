"""``migrate_database`` adds the account_model columns in ``ACCOUNT_COLUMNS`` to an
existing database, leaving existing data and already-present columns alone."""

import logging
import sqlite3

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models.account import AccountModel
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.migrations import ACCOUNT_COLUMNS, migrate_database

NEW_COLUMNS = {"cooldown_hours", "consent_expires_at", "consent_reminder_sent_at", "include_pending_credits"}

BASE_COLUMNS = """
    id INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL UNIQUE,
    provider VARCHAR(50),
    access_token VARCHAR(255) NOT NULL,
    refresh_token VARCHAR(255) NOT NULL,
    token_expiry INTEGER,
    pot_id VARCHAR(255),
    account_id VARCHAR(255),
    cooldown_until INTEGER,
    prev_balance INTEGER,
    cooldown_ref_card_balance INTEGER,
    cooldown_ref_pot_balance INTEGER,
    stable_pot_balance INTEGER
"""


def _legacy_database(path, extra_columns=""):
    connection = sqlite3.connect(path)
    connection.execute(f"CREATE TABLE account_model ({BASE_COLUMNS}{extra_columns}, PRIMARY KEY (id))")
    connection.execute(
        "INSERT INTO account_model (id, type, provider, access_token, refresh_token, pot_id, prev_balance) "
        "VALUES (1, 'American Express', 'American Express', 'acc', 'ref', 'amex_pot', 4200)"
    )
    connection.commit()
    connection.close()


def _app(path):
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}", "SECRET_KEY": "testing"})


def _columns():
    return {column["name"]: column for column in inspect(db.engine).get_columns("account_model")}


def test_account_columns_cover_the_new_fields():
    assert set(ACCOUNT_COLUMNS) == NEW_COLUMNS
    for column in ACCOUNT_COLUMNS:
        assert hasattr(AccountModel, column)


def test_existing_database_gains_every_new_column(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_database(path)

    app = _app(path)  # create_app runs the migration

    with app.app_context():
        columns = _columns()
        assert NEW_COLUMNS <= set(columns)
        for name in ("cooldown_hours", "consent_expires_at", "consent_reminder_sent_at"):
            assert str(columns[name]["type"]) == "INTEGER"
            assert columns[name]["nullable"]
        assert str(columns["include_pending_credits"]["type"]) == "BOOLEAN"

        account = db.session.get(AccountModel, 1)
        assert account.cooldown_hours is None
        assert account.consent_expires_at is None
        assert account.consent_reminder_sent_at is None
        assert account.pot_id == "amex_pot"
        assert account.prev_balance == 4200

        # And the columns are usable straight away.
        repository = SqlAlchemyAccountRepository(db)
        repository.set_cooldown_hours("American Express", 5)
        repository.set_consent_expiry("American Express", 1_900_000_000)
        repository.mark_consent_reminder_sent("American Express", 1_800_000_000)
        card = repository.get("American Express")
        assert (card.cooldown_hours, card.consent_expires_at, card.consent_reminder_sent_at) == (
            5,
            1_900_000_000,
            1_800_000_000,
        )


def test_only_missing_columns_are_added(tmp_path, caplog):
    # A database from the release that added include_pending_credits and cooldown_hours.
    path = tmp_path / "partial.db"
    _legacy_database(path, ",\n include_pending_credits BOOLEAN,\n cooldown_hours INTEGER")
    connection = sqlite3.connect(path)
    connection.execute("UPDATE account_model SET include_pending_credits = 0, cooldown_hours = 7")
    connection.commit()
    connection.close()

    with caplog.at_level(logging.INFO, logger="migrations"):
        app = _app(path)

    assert "Adding account_model.consent_expires_at" in caplog.text
    assert "Adding account_model.consent_reminder_sent_at" in caplog.text
    assert "Adding account_model.cooldown_hours" not in caplog.text
    assert "Adding account_model.include_pending_credits" not in caplog.text
    with app.app_context():
        assert NEW_COLUMNS <= set(_columns())
        account = db.session.get(AccountModel, 1)
        assert account.include_pending_credits is False
        assert account.cooldown_hours == 7
        assert account.consent_expires_at is None


def test_migration_is_idempotent(tmp_path, caplog):
    path = tmp_path / "legacy.db"
    _legacy_database(path)
    app = _app(path)

    with app.app_context(), caplog.at_level(logging.INFO, logger="migrations"):
        caplog.clear()
        migrate_database(db)
        assert "Adding account_model" not in caplog.text
        assert NEW_COLUMNS <= set(_columns())
