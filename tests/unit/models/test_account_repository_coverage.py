from time import time

import pytest
from sqlalchemy.exc import NoResultFound

from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.extensions import db
from app.models.account import AccountModel
from app.models.account_repository import SqlAlchemyAccountRepository


@pytest.fixture
def repository(test_client):
    return SqlAlchemyAccountRepository(db)


def _card(name, provider=None, **kwargs):
    return TrueLayerAccount(name, "access", "refresh", int(time()) + 1000, "pot", provider_type=provider, **kwargs)


def test_get_all_returns_every_account_in_insertion_order(repository):
    repository.save(_card("Barclaycard"))
    repository.save(MonzoAccount("m_access", "m_refresh", 123, "monzo_pot"))
    repository.save(_card("American Express 2", provider="American Express", prev_balance=4200))

    accounts = repository.get_all()

    assert [a.type for a in accounts] == ["Barclaycard", "Monzo", "American Express 2"]
    assert [a.provider_type for a in accounts] == ["Barclaycard", "Monzo", "American Express"]
    assert accounts[1].access_token == "m_access"
    assert accounts[1].pot_id == "monzo_pot"
    assert accounts[2].prev_balance == 4200


def test_get_all_empty(repository):
    assert repository.get_all() == []


def test_get_next_account_name_first_connection(repository):
    assert repository.get_next_account_name("Barclaycard") == "Barclaycard"


def test_get_next_account_name_uses_highest_numbered_suffix(repository):
    repository.save(_card("Barclaycard"))
    repository.save(_card("Barclaycard 3", provider="Barclaycard"))
    repository.save(_card("Barclaycard 2", provider="Barclaycard"))
    # Names that are not "<provider> <number>" do not affect numbering.
    repository.save(_card("Barclaycard Work", provider="Barclaycard"))

    assert repository.get_next_account_name("Barclaycard") == "Barclaycard 4"


def test_get_next_account_name_matches_legacy_rows_without_provider(test_client, repository):
    # Rows saved before the ``provider`` column existed have provider=NULL.
    db.session.add_all([
        AccountModel(type="Lloyds", access_token="a", refresh_token="r"),
        AccountModel(type="Lloyds 5", access_token="a", refresh_token="r"),
    ])
    db.session.commit()

    assert repository.get_next_account_name("Lloyds") == "Lloyds 6"


def test_get_next_account_name_ignores_other_providers(repository):
    repository.save(_card("Halifax"))
    repository.save(_card("Halifax 7", provider="Halifax"))

    assert repository.get_next_account_name("Lloyds") == "Lloyds"


def test_get_missing_account_raises(repository):
    with pytest.raises(NoResultFound, match="Account with type 'NatWest' not found."):
        repository.get("NatWest")


def test_update_credit_account_fields_sets_cooldown_and_reference(repository):
    repository.save(_card("Barclaycard", prev_balance=100))

    updated = repository.update_credit_account_fields(
        "Barclaycard", "pot", new_balance=5000, cooldown_until=9999999999, cooldown_ref_card_balance=4800
    )

    assert updated.prev_balance == 5000
    assert updated.cooldown_until == 9999999999
    assert updated.cooldown_ref_card_balance == 4800
    stored = repository.get("Barclaycard")
    assert stored.cooldown_until == 9999999999
    assert stored.cooldown_ref_card_balance == 4800


def test_update_credit_account_fields_keeps_reference_when_not_supplied(repository):
    repository.save(_card("Barclaycard", cooldown_until=9999999999, cooldown_ref_card_balance=4800))

    updated = repository.update_credit_account_fields(
        "Barclaycard", "pot", new_balance=6000, cooldown_until=9999999999
    )

    assert updated.prev_balance == 6000
    assert updated.cooldown_ref_card_balance == 4800


def test_update_credit_account_fields_clearing_cooldown_clears_reference(repository):
    repository.save(_card("Barclaycard", cooldown_until=9999999999, cooldown_ref_card_balance=4800))

    updated = repository.update_credit_account_fields(
        "Barclaycard", "pot", new_balance=7000, cooldown_until=None, cooldown_ref_card_balance=1234
    )

    assert updated.cooldown_until is None
    assert updated.cooldown_ref_card_balance is None
