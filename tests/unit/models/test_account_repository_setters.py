"""The single-field setters on ``SqlAlchemyAccountRepository`` added for per-card
cooldowns, consent expiry reminders and reconnecting."""

from time import time

import pytest
from sqlalchemy.exc import NoResultFound

from app.domain.accounts import TrueLayerAccount
from app.domain.auth_providers import AuthProviderType
from app.extensions import db
from app.models.account import AccountModel
from app.models.account_repository import SqlAlchemyAccountRepository

AMEX = AuthProviderType.AMEX.value


@pytest.fixture
def repository(test_client, seed_data):
    return SqlAlchemyAccountRepository(db)


def _row(account_type=AMEX):
    db.session.expire_all()
    return AccountModel.query.filter_by(type=account_type).one()


def _card(repository, account_type=AMEX):
    return next(a for a in repository.get_credit_accounts() if a.type == account_type)


def test_new_fields_default_to_none(repository):
    card = _card(repository)

    assert card.cooldown_hours is None
    assert card.consent_expires_at is None
    assert card.consent_reminder_sent_at is None


def test_new_fields_are_saved_for_a_new_connection(repository):
    repository.save(
        TrueLayerAccount(
            "Barclaycard", "a", "r", 1, "pot", provider_type="Barclaycard",
            cooldown_hours=8, consent_expires_at=111, consent_reminder_sent_at=99,
        )
    )

    card = repository.get("Barclaycard")
    assert (card.cooldown_hours, card.consent_expires_at, card.consent_reminder_sent_at) == (8, 111, 99)


def test_set_cooldown_hours(repository):
    repository.set_cooldown_hours(AMEX, 12)
    assert _row().cooldown_hours == 12
    assert _card(repository).cooldown_hours == 12
    assert repository.get(AMEX).cooldown_hours == 12

    repository.set_cooldown_hours(AMEX, None)
    assert _row().cooldown_hours is None


def test_set_consent_expiry(repository):
    repository.set_consent_expiry(AMEX, 1_900_000_000)
    assert _row().consent_expires_at == 1_900_000_000
    assert _card(repository).consent_expires_at == 1_900_000_000

    repository.set_consent_expiry(AMEX, None)
    assert _row().consent_expires_at is None


def test_mark_consent_reminder_sent(repository):
    repository.mark_consent_reminder_sent(AMEX, 1_800_000_000)

    assert _row().consent_reminder_sent_at == 1_800_000_000
    assert _card(repository).consent_reminder_sent_at == 1_800_000_000


def test_update_tokens_keeps_everything_but_tokens_and_consent(repository):
    record = _row()
    record.pot_id = "amex_pot"
    record.account_id = "acc_1"
    record.prev_balance = 4200
    record.cooldown_until = 1_800_000_000
    record.cooldown_ref_card_balance = 5000
    record.cooldown_ref_pot_balance = 3000
    record.stable_pot_balance = 4000
    record.include_pending_credits = False
    record.cooldown_hours = 6
    record.consent_expires_at = 1_700_000_000
    record.consent_reminder_sent_at = 1_699_000_000
    db.session.commit()

    repository.update_tokens(AMEX, "new_access", "new_refresh", 1_234)

    record = _row()
    assert (record.access_token, record.refresh_token, record.token_expiry) == ("new_access", "new_refresh", 1_234)
    assert record.consent_expires_at is None
    assert record.consent_reminder_sent_at is None
    assert record.type == AMEX
    assert record.provider == AMEX
    assert record.pot_id == "amex_pot"
    assert record.account_id == "acc_1"
    assert record.prev_balance == 4200
    assert record.cooldown_until == 1_800_000_000
    assert record.cooldown_ref_card_balance == 5000
    assert record.cooldown_ref_pot_balance == 3000
    assert record.stable_pot_balance == 4000
    assert record.include_pending_credits is False
    assert record.cooldown_hours == 6


def test_setters_only_touch_the_named_connection(repository):
    repository.save(TrueLayerAccount(f"{AMEX} 2", "a2", "r2", int(time()), "pot_2", provider_type=AMEX))

    repository.set_cooldown_hours(f"{AMEX} 2", 5)
    repository.set_consent_expiry(f"{AMEX} 2", 10)
    repository.mark_consent_reminder_sent(f"{AMEX} 2", 20)
    repository.update_tokens(f"{AMEX} 2", "x", "y", 30)

    first = _row(AMEX)
    assert first.cooldown_hours is None
    assert first.consent_expires_at is None
    assert first.consent_reminder_sent_at is None
    assert first.access_token == "access_token"
    assert _row(f"{AMEX} 2").access_token == "x"


def test_save_does_not_undo_a_setter_change(repository):
    # The sync saves copies it loaded at the start of a run; that must not revert a
    # cooldown length or consent expiry changed meanwhile.
    loaded = _card(repository)
    repository.set_cooldown_hours(AMEX, 9)
    repository.set_consent_expiry(AMEX, 123)
    repository.mark_consent_reminder_sent(AMEX, 45)

    repository.save(loaded)

    record = _row()
    assert record.cooldown_hours == 9
    assert record.consent_expires_at == 123
    assert record.consent_reminder_sent_at == 45


@pytest.mark.parametrize(
    "call",
    [
        lambda repo: repo.set_cooldown_hours("Nope", 1),
        lambda repo: repo.set_consent_expiry("Nope", 1),
        lambda repo: repo.mark_consent_reminder_sent("Nope", 1),
        lambda repo: repo.update_tokens("Nope", "a", "r", 1),
    ],
)
def test_setters_raise_for_an_unknown_connection(repository, call):
    with pytest.raises(NoResultFound):
        call(repository)
