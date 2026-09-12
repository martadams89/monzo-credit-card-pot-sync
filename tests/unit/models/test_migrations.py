import sqlite3

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models.account import AccountModel
from app.models.migrations import migrate_database


def test_existing_database_is_migrated_without_losing_account_data(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE account_model (
            id INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL UNIQUE,
            access_token VARCHAR(255) NOT NULL,
            refresh_token VARCHAR(255) NOT NULL,
            token_expiry INTEGER,
            pot_id VARCHAR(255),
            account_id VARCHAR(255),
            cooldown_until INTEGER,
            prev_balance INTEGER,
            cooldown_ref_card_balance INTEGER,
            cooldown_ref_pot_balance INTEGER,
            stable_pot_balance INTEGER,
            PRIMARY KEY (id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO account_model (
            id, type, access_token, refresh_token, token_expiry, pot_id,
            prev_balance, cooldown_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            7,
            "American Express",
            "existing_access",
            "existing_refresh",
            1234567890,
            "existing_pot",
            4200,
            1234567000,
        ),
    )
    connection.commit()
    connection.close()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "SECRET_KEY": "testing",
        }
    )

    with app.app_context():
        migrate_database(db)
        column_names = {
            column["name"] for column in inspect(db.engine).get_columns("account_model")
        }
        account = db.session.get(AccountModel, 7)

        assert "provider" in column_names
        assert account.type == "American Express"
        assert account.provider == "American Express"
        assert account.access_token == "existing_access"
        assert account.pot_id == "existing_pot"
        assert account.prev_balance == 4200
        assert account.cooldown_until == 1234567000


def test_migration_clears_the_placeholder_cooldown_reference_balance(tmp_path):
    """The column used to default to 0, which the sync read as a real card balance.

    A cooldown only opens while the card is above the pot, so a stored 0 is always the
    old default rather than a balance a cooldown was opened against. Left in place it
    ended every cooldown on the next run.
    """
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE account_model (
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
            stable_pot_balance INTEGER,
            PRIMARY KEY (id)
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO account_model (
            id, type, provider, access_token, refresh_token, token_expiry, pot_id,
            prev_balance, cooldown_until, cooldown_ref_card_balance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "American Express",
                "American Express",
                "access",
                "refresh",
                1234567890,
                "amex_pot",
                196327,
                1234567000,
                0,
            ),
            (
                2,
                "Barclaycard",
                "Barclaycard",
                "access",
                "refresh",
                1234567890,
                "barclaycard_pot",
                4498,
                1234567000,
                44980,
            ),
        ],
    )
    connection.commit()
    connection.close()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "SECRET_KEY": "testing",
        }
    )

    with app.app_context():
        migrate_database(db)

        amex = db.session.get(AccountModel, 1)
        barclaycard = db.session.get(AccountModel, 2)

        assert amex.cooldown_ref_card_balance is None
        assert amex.cooldown_until == 1234567000
        assert amex.prev_balance == 196327
        # A genuine reference is left untouched.
        assert barclaycard.cooldown_ref_card_balance == 44980
