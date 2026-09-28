"""``TrueLayerAccount.ping()`` checks the connection and returns when its consent
expires, from TrueLayer's /data/v1/me."""

import datetime
from time import time

import pytest

from app.domain.accounts import TrueLayerAccount

ME_URL = "https://api.truelayer.com/data/v1/me"


def _account():
    return TrueLayerAccount("American Express", "access_token", "refresh_token", int(time()) + 1000)


def _epoch(*args, tz=datetime.timezone.utc):
    return int(datetime.datetime(*args, tzinfo=tz).timestamp())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-12-01T10:00:00Z", _epoch(2026, 12, 1, 10, 0, 0)),
        ("2026-12-01T10:00:00.123Z", _epoch(2026, 12, 1, 10, 0, 0)),
        ("2026-12-01T10:00:00+00:00", _epoch(2026, 12, 1, 10, 0, 0)),
        ("2026-12-01T11:00:00+01:00", _epoch(2026, 12, 1, 10, 0, 0)),
    ],
)
def test_ping_returns_consent_expiry_as_epoch_seconds(requests_mock, value, expected):
    requests_mock.get(
        ME_URL,
        json={"results": [{"client_id": "c", "credentials_id": "x", "consent_expires_at": value}], "status": "Succeeded"},
    )

    assert _account().ping() == expected


def test_ping_sends_the_access_token(requests_mock):
    requests_mock.get(ME_URL, json={"results": [{"consent_expires_at": "2026-12-01T10:00:00Z"}]})

    _account().ping()

    assert requests_mock.last_request.headers["Authorization"] == "Bearer access_token"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": ""},  # no body
        {"text": "not json"},
        {"json": {}},  # no results
        {"json": {"results": []}},
        {"json": {"results": [{}]}},  # no expiry
        {"json": {"results": [{"consent_expires_at": None}]}},
        {"json": {"results": [{"consent_expires_at": "next tuesday"}]}},
        {"json": {"results": [{"consent_expires_at": 1_900_000_000}]}},
        {"json": {"results": "oops"}},
        {"json": {"results": ["oops"]}},
        {"json": ["unexpected"]},
    ],
)
def test_ping_returns_none_when_expiry_unknown(requests_mock, kwargs):
    requests_mock.get(ME_URL, **kwargs)

    assert _account().ping() is None


def test_ping_error_response_returns_none(requests_mock):
    requests_mock.get(ME_URL, status_code=500, json={"error": "provider_error"})

    assert _account().ping() is None
