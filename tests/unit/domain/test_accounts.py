from time import time
from urllib import parse
from app.domain.accounts import MonzoAccount, TrueLayerAccount

def test_truelayer_account_get_card_balance(mocker, requests_mock):
    # Mock the auth provider
    mock_auth_provider = mocker.Mock()
    mock_auth_provider.api_url = "https://api.truelayer.com"
    mocker.patch("app.domain.accounts.provider_mapping", {"TrueLayer": mock_auth_provider})

    # Create a TrueLayerAccount instance
    account = TrueLayerAccount(type="TrueLayer", access_token="access_token")

    # Mock the balance and pending transactions endpoints
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/1/balance",
        json={"results": [{"current": 1000}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/1/transactions/pending",
        json={
            "results": [
                {"transaction_id": "txn1", "amount": 10.0, "currency": "GBP"},
                {"transaction_id": "txn2", "amount": 5.0, "currency": "GBP"},
            ]
        },
    )

    # Call the method and assert the result
    balance = account.get_card_balance("1")
    assert balance == 1015.0


def test_truelayer_account_get_total_balance(mocker, requests_mock):
    # Mock the auth provider
    mock_auth_provider = mocker.Mock()
    mock_auth_provider.api_url = "https://api.truelayer.com"
    mocker.patch("app.domain.accounts.provider_mapping", {"TrueLayer": mock_auth_provider})

    # Create a TrueLayerAccount instance
    account = TrueLayerAccount(type="TrueLayer", access_token="access_token")

    # Mock the cards, balance, and pending transactions endpoints
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "1"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/1/balance",
        json={"results": [{"current": 1000}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/1/transactions/pending",
        json={
            "results": [
                {"transaction_id": "txn1", "amount": 10.0, "currency": "GBP"},
                {"transaction_id": "txn2", "amount": 5.0, "currency": "GBP"},
            ]
        },
    )

    # Call the method and assert the result
    total_balance = account.get_total_balance()
    assert total_balance == 101500