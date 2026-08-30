from urllib.parse import urlparse

from app.domain.accounts import TrueLayerAccount
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository


def test_get_pots(test_client, requests_mock, seed_data):
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_123", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/pots?current_account_id=acc_123",
        json={
            "pots": [
                {"id": "pot_123", "name": "Pot 1", "balance": 100, "deleted": False}
            ]
        },
    )
    response = test_client.get("/pots/")
    assert response.status_code == 200
    assert b"Pot 1" in response.data
    assert b'data-tabs-inactive-classes="text-gray-500' in response.data
    assert b'data-tabs-inactive-classes="text-white' not in response.data

def test_get_pots_no_account(test_client):
    response = test_client.get("/pots/")
    assert response.status_code == 200
    assert b"You need to connect a Monzo account" in response.data


def test_get_pots_shows_each_connection_from_the_same_provider(
    test_client, requests_mock, seed_data
):
    SqlAlchemyAccountRepository(db).save(
        TrueLayerAccount(
            "American Express 2",
            "second_access_token",
            "second_refresh_token",
            1234567890,
            "second_pot",
            provider_type="American Express",
        )
    )
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_123", "type": "uk_retail"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/pots?current_account_id=acc_123",
        json={"pots": []},
    )

    response = test_client.get("/pots/?account=personal")

    assert response.status_code == 200
    assert b'id="AmericanExpress-tab"' in response.data
    assert b'id="AmericanExpress2-tab"' in response.data
    assert b"American Express 2" in response.data

def test_post_pots(test_client, requests_mock, seed_data):
    # Submit a request to set the designated pot for a given credit card account
    response = test_client.post(
        "/pots/", data={"account_type": "American Express", "pot_id": "pot_123"}
    )
    assert response.status_code == 302
    assert urlparse(response.location).path == "/pots/"

    # Following the update, fetch the pots page to verify changes are reflected.
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_123", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/pots?current_account_id=acc_123",
        json={
            "pots": [
                {"id": "pot_123", "name": "Pot 1", "balance": 100, "deleted": False}
            ]
        },
    )
    response = test_client.get("/pots/")
    assert response.status_code == 200
    assert b"Pot 1" in response.data
    # Verify that the designated pot indicator appears as expected
    assert b"Credit Card pot" in response.data


def test_post_pots_updates_selected_provider_connection(test_client, seed_data):
    repository = SqlAlchemyAccountRepository(db)
    repository.save(
        TrueLayerAccount(
            "American Express 2",
            "second_access_token",
            "second_refresh_token",
            1234567890,
            "second_original_pot",
            provider_type="American Express",
        )
    )

    response = test_client.post(
        "/pots/",
        data={"account_type": "American Express 2", "pot_id": "second_new_pot"},
    )

    assert response.status_code == 302
    assert repository.get("American Express").pot_id == "pot_id"
    assert repository.get("American Express 2").pot_id == "second_new_pot"
