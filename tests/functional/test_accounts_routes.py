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
