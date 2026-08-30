from urllib.parse import urlparse

import pytest

from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository


def test_monzo_oauth_callback(test_client, requests_mock):
    requests_mock.post(
        "https://api.monzo.com/oauth2/token",
        json={"access_token": "access", "refresh_token": "refresh", "expires_in": 1000},
    )
    response = test_client.get("/auth/callback/monzo?code=123&state=Monzo-123")
    assert response.status_code == 302
    assert urlparse(response.location).path == "/accounts/"

def test_truelayer_oauth_callback(test_client, requests_mock):
    requests_mock.post(
        "https://auth.truelayer.com/connect/token",
        json={"access_token": "access", "refresh_token": "refresh", "expires_in": 1000},
    )
    response = test_client.get("/auth/callback/truelayer?code=123&state=Barclaycard-123")
    assert response.status_code == 302
    assert urlparse(response.location).path == "/accounts/"


def test_truelayer_oauth_callback_allows_multiple_accounts_from_same_provider(
    test_client, requests_mock
):
    requests_mock.post(
        "https://auth.truelayer.com/connect/token",
        [
            {
                "json": {
                    "access_token": "access-one",
                    "refresh_token": "refresh-one",
                    "expires_in": 1000,
                }
            },
            {
                "json": {
                    "access_token": "access-two",
                    "refresh_token": "refresh-two",
                    "expires_in": 1000,
                }
            },
        ],
    )

    first_response = test_client.get(
        "/auth/callback/truelayer?code=123&state=American%20Express-123"
    )
    second_response = test_client.get(
        "/auth/callback/truelayer?code=456&state=American%20Express-456"
    )

    assert first_response.status_code == 302
    assert second_response.status_code == 302

    accounts = SqlAlchemyAccountRepository(db).get_credit_accounts()
    assert [account.type for account in accounts] == [
        "American Express",
        "American Express 2",
    ]
    assert [account.provider_type for account in accounts] == [
        "American Express",
        "American Express",
    ]
    assert accounts[0].access_token == "access-one"
    assert accounts[1].access_token == "access-two"

def test_monzo_oauth_callback_missing_token(test_client, requests_mock):
    # Simulate token endpoint returning an error (missing required fields)
    requests_mock.post(
        "https://api.monzo.com/oauth2/token",
        json={"error": "invalid_request"},
        status_code=400
    )
    with pytest.raises(KeyError):
        test_client.get("/auth/callback/monzo?code=123&state=Monzo-123")

def test_truelayer_oauth_callback_missing_token(test_client, requests_mock):
    # Simulate token endpoint returning an empty response (missing access_token)
    requests_mock.post(
        "https://auth.truelayer.com/connect/token",
        json={},
        status_code=400
    )
    with pytest.raises(KeyError):
        test_client.get("/auth/callback/truelayer?code=123&state=Barclaycard-123")
