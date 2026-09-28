from urllib.parse import urlparse

from app.domain.accounts import TrueLayerAccount
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository


def test_get_accounts(test_client, seed_data):
    response = test_client.get("/accounts/")
    assert response.status_code == 200
    assert b"Accounts" in response.data
    assert b"Monzo" in response.data
    # Check for a sample credit provider
    assert b"American Express" in response.data

def test_get_accounts_no_accounts(test_client):
    response = test_client.get("/accounts/")
    assert response.status_code == 200
    assert b"Accounts" in response.data

def test_post_deletes_account(test_client, seed_data):
    response = test_client.post("/accounts/", data={"account_type": "American Express"})
    assert response.status_code == 302
    assert urlparse(response.location).path == "/accounts/"
    assert b"American Express" not in response.data


def test_post_deletes_only_selected_provider_connection(test_client, seed_data):
    repository = SqlAlchemyAccountRepository(db)
    repository.save(
        TrueLayerAccount(
            "American Express 2",
            "second_access_token",
            "second_refresh_token",
            1234567890,
            provider_type="American Express",
        )
    )

    response = test_client.post(
        "/accounts/", data={"account_type": "American Express 2"}
    )

    assert response.status_code == 302
    assert repository.get("American Express").type == "American Express"
    assert [account.type for account in repository.get_credit_accounts()] == [
        "American Express"
    ]


def test_get_add_account_shows_providers(test_client):
    response = test_client.get("/accounts/add")
    assert response.status_code == 200
    assert b"Monzo" in response.data
    assert b"American Express" in response.data
    assert b"Barclaycard" in response.data
    assert b"Halifax" in response.data
    assert b"Lloyds" in response.data
    assert b"NatWest" in response.data


def test_post_deleting_an_unknown_account_is_ignored(test_client, seed_data):
    response = test_client.post("/accounts/", data={"account_type": "Not Connected"})
    assert response.status_code == 302
    assert urlparse(response.location).path == "/accounts/"
    assert len(SqlAlchemyAccountRepository(db).get_credit_accounts()) == 1


def test_pending_credits_toggle_shown_only_for_amex_and_lloyds(test_client, seed_data):
    repository = SqlAlchemyAccountRepository(db)
    repository.save(TrueLayerAccount("Lloyds", "a", "r", 9999999999, "pot_2", provider_type="Lloyds"))
    repository.save(TrueLayerAccount("Barclaycard", "a", "r", 9999999999, "pot_3", provider_type="Barclaycard"))

    data = test_client.get("/accounts/").data
    assert data.count(b'name="include_pending_credits"') == 2
    assert data.count(b"onchange=\"this.form.submit()\" checked") == 2


def test_pending_credits_toggle_is_per_connection(test_client, seed_data):
    repository = SqlAlchemyAccountRepository(db)
    repository.save(TrueLayerAccount("American Express 2", "a", "r", 9999999999, "pot_2", provider_type="American Express"))

    # Unchecked: the checkbox is missing from the form.
    response = test_client.post("/accounts/pending_credits", data={"account_type": "American Express"}, follow_redirects=True)
    assert b"no longer counted for American Express" in response.data

    accounts = {a.type: a for a in repository.get_credit_accounts()}
    assert accounts["American Express"].include_pending_credits is False
    assert accounts["American Express 2"].include_pending_credits is True

    test_client.post("/accounts/pending_credits", data={"account_type": "American Express", "include_pending_credits": "on"})
    assert repository.get("American Express").include_pending_credits is True


def test_pending_credits_toggle_for_unknown_account(test_client, seed_data):
    response = test_client.post("/accounts/pending_credits", data={"account_type": "Nope"}, follow_redirects=True)
    assert b"Account not found" in response.data


def test_sync_save_does_not_undo_pending_credits_toggle(test_client, seed_data):
    # The sync saves the copies it loaded at the start of a run; that must not put
    # back a toggle the user changed while it was running.
    repository = SqlAlchemyAccountRepository(db)
    stale = repository.get_credit_accounts()[0]
    repository.set_include_pending_credits(stale.type, False)

    repository.save(stale)
    assert repository.get(stale.type).include_pending_credits is False
