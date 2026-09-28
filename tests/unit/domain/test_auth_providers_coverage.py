from urllib import parse

import pytest

from app.domain.auth_providers import (
    AuthProvider,
    AuthProviderType,
    BarclaycardAuthProvider,
    HalifaxAuthProvider,
    LloydsAuthProvider,
    NatWestAuthProvider,
    TrueLayerAuthProvider,
    provider_mapping,
)
from app.errors import AuthException


def test_base_provider_has_no_specific_oauth_params():
    assert AuthProvider.get_provider_specific_oauth_request_params() == {}


def test_generic_truelayer_provider_oauth_url_has_only_default_params(setting_repository):
    provider = TrueLayerAuthProvider("TrueLayer", "truelayer", "truelayer.svg")

    url = provider.create_oauth_request_url()

    base, query = url.split("?", 1)
    assert base == "https://auth.truelayer.com"
    params = parse.parse_qs(query)
    assert set(params) == {"client_id", "response_type", "redirect_uri", "state"}
    assert params["client_id"] == ["setting_value"]
    assert params["redirect_uri"] == [provider.callback_url]
    assert params["state"][0].startswith("truelayer-")


@pytest.mark.parametrize(
    ("provider_cls", "provider_id"),
    [
        (BarclaycardAuthProvider, "uk-ob-barclaycard"),
        (HalifaxAuthProvider, "uk-ob-halifax"),
        (LloydsAuthProvider, "uk-ob-lloyds"),
        (NatWestAuthProvider, "uk-ob-natwest"),
    ],
)
def test_truelayer_card_provider_oauth_url(setting_repository, provider_cls, provider_id):
    provider = provider_cls()

    params = parse.parse_qs(provider.create_oauth_request_url().split("?", 1)[1])

    assert params["providers"] == [provider_id]
    assert params["scope"] == ["accounts balance transactions cards offline_access"]
    assert params["state"][0].startswith(f"{provider.type}-")


def test_handle_oauth_code_callback_non_json_response_raises(setting_repository, requests_mock, monzo_provider):
    token = requests_mock.post(monzo_provider.get_token_url(), status_code=502, text="<html>Bad gateway</html>")

    with pytest.raises(AuthException, match="No access token returned"):
        monzo_provider.handle_oauth_code_callback("the_code")

    body = parse.parse_qs(token.last_request.text)
    assert body["code"] == ["the_code"]
    assert body["grant_type"] == ["authorization_code"]


def test_provider_mapping_covers_every_provider_type():
    assert set(provider_mapping) == set(AuthProviderType)
    for provider_type, provider in provider_mapping.items():
        assert provider.type == provider_type.value
