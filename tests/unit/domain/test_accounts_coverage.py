from time import time
from urllib import parse

import pytest

from app.domain.accounts import Account, MonzoAccount, TrueLayerAccount
from app.errors import AuthException, PotNotFoundError, PotTransferError

MONZO = "https://api.monzo.com"
TRUELAYER = "https://api.truelayer.com/data/v1"

ALL_ACCOUNTS = {
    "accounts": [
        {"id": "acc_personal", "type": "uk_retail", "description": "user_personal"},
        {"id": "acc_joint", "type": "uk_retail_joint", "description": "joint desc"},
        {"id": "acc_business", "type": "uk_business"},
    ]
}


def _pots_url(account_id):
    return f"{MONZO}/pots?{parse.urlencode({'current_account_id': account_id})}"


def _monzo():
    return MonzoAccount("access_token", "refresh_token", int(time()) + 1000)


def _mock_pots(requests_mock, personal=(), joint=(), business=()):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    requests_mock.get(_pots_url("acc_personal"), json={"pots": list(personal)})
    requests_mock.get(_pots_url("acc_joint"), json={"pots": list(joint)})
    requests_mock.get(_pots_url("acc_business"), json={"pots": list(business)})


def _pot(pot_id, balance=0, deleted=False):
    return {"id": pot_id, "balance": balance, "deleted": deleted}


# --------------------------------------------------------------------------- #
# Account.refresh_access_token
# --------------------------------------------------------------------------- #


class _StubProvider:
    def __init__(self, tokens):
        self.tokens = tokens
        self.received = None

    def refresh_access_token(self, refresh_token):
        self.received = refresh_token
        return self.tokens


def test_refresh_access_token_updates_tokens_and_expiry():
    account = TrueLayerAccount("American Express", "old_access", "old_refresh", 0)
    account.auth_provider = _StubProvider(
        {"access_token": "new_access", "refresh_token": "new_refresh", "expires_in": 3600}
    )

    before = int(time())
    account.refresh_access_token()

    assert account.auth_provider.received == "old_refresh"
    assert account.access_token == "new_access"
    assert account.refresh_token == "new_refresh"
    assert before + 3600 <= account.token_expiry <= int(time()) + 3600
    assert not account.is_token_within_expiry_window()


def test_refresh_access_token_missing_expires_in_raises_auth_exception():
    account = TrueLayerAccount("American Express", "old_access", "old_refresh", 0)
    account.auth_provider = _StubProvider({"access_token": "a", "refresh_token": "r"})

    with pytest.raises(AuthException, match="Unexpected token response format") as excinfo:
        account.refresh_access_token()

    assert isinstance(excinfo.value.__cause__, KeyError)


def test_refresh_access_token_missing_fields_attaches_details():
    account = TrueLayerAccount("American Express", "old_access", "old_refresh", 0)
    response = {"error": "invalid_grant"}
    account.auth_provider = _StubProvider(response)

    with pytest.raises(AuthException, match="missing required fields") as excinfo:
        account.refresh_access_token()

    assert excinfo.value.details == response
    # Tokens are untouched on failure.
    assert account.access_token == "old_access"
    assert account.refresh_token == "old_refresh"


# --------------------------------------------------------------------------- #
# Account.pre_deposit_check / get_prev_balance
# --------------------------------------------------------------------------- #


def test_pre_deposit_check_allows_increase_without_touching_cooldown():
    account = Account("Barclaycard")
    assert account.pre_deposit_check(current_balance=1000, new_balance=1500, cooldown_duration=60)
    assert account.cooldown_until is None


def test_pre_deposit_check_allows_unchanged_balance():
    account = Account("Barclaycard")
    assert account.pre_deposit_check(1000, 1000, 60)
    assert account.cooldown_until is None


def test_pre_deposit_check_decrease_starts_cooldown():
    account = Account("Barclaycard")
    before = int(time())

    assert account.pre_deposit_check(1000, 500, 3600) is False
    assert before + 3600 <= account.cooldown_until <= int(time()) + 3600


def test_pre_deposit_check_decrease_during_active_cooldown_keeps_existing_cooldown():
    active_until = int(time()) + 500
    account = Account("Barclaycard", cooldown_until=active_until)

    assert account.pre_deposit_check(1000, 500, 3600) is False
    assert account.cooldown_until == active_until


def test_pre_deposit_check_decrease_after_expired_cooldown_starts_new_one():
    account = Account("Barclaycard", cooldown_until=int(time()) - 10)
    before = int(time())

    assert account.pre_deposit_check(1000, 500, 60) is False
    assert account.cooldown_until >= before + 60


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(1234, 1234), ("567", 567), (None, 0), ("not-a-number", 0), ([1], 0)],
)
def test_get_prev_balance(stored, expected):
    account = Account("Barclaycard", prev_balance=stored)
    assert account.get_prev_balance("pot") == expected


# --------------------------------------------------------------------------- #
# MonzoAccount lookups
# --------------------------------------------------------------------------- #


def test_get_authorized_accounts_excludes_closed(requests_mock):
    requests_mock.get(
        f"{MONZO}/accounts",
        json={"accounts": [
            {"id": "open", "type": "uk_retail"},
            {"id": "closed", "type": "uk_retail", "closed": True},
            {"id": "explicit_open", "type": "uk_retail_joint", "closed": False},
        ]},
    )
    ids = [a["id"] for a in _monzo().get_authorized_accounts()]
    assert ids == ["open", "explicit_open"]


def test_get_account_id_unknown_selection_falls_back_to_personal(requests_mock):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    assert _monzo().get_account_id("savings") == "acc_personal"


def test_get_account_id_skips_closed_account(requests_mock):
    requests_mock.get(
        f"{MONZO}/accounts",
        json={"accounts": [
            {"id": "old", "type": "uk_retail", "closed": True},
            {"id": "new", "type": "uk_retail"},
        ]},
    )
    assert _monzo().get_account_id() == "new"


def test_get_account_id_raises_when_type_missing(requests_mock):
    requests_mock.get(f"{MONZO}/accounts", json={"accounts": [{"id": "p", "type": "uk_retail"}]})
    with pytest.raises(AuthException, match="No account found for type: uk_retail_joint"):
        _monzo().get_account_id("joint")


def test_get_account_description(requests_mock):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    account = _monzo()
    assert account.get_account_description() == "user_personal"
    assert account.get_account_description("joint") == "joint desc"
    # No description field at all -> empty string.
    assert account.get_account_description("business") == ""


def test_get_account_description_returns_empty_when_account_disappears(requests_mock):
    # The account is found on the first fetch but gone on the second.
    requests_mock.get(
        f"{MONZO}/accounts",
        [
            {"json": {"accounts": [{"id": "p", "type": "uk_retail", "description": "d"}]}},
            {"json": {"accounts": []}},
        ],
    )
    assert _monzo().get_account_description() == ""


def test_get_balance_queries_selected_account(requests_mock):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    balance = requests_mock.get(f"{MONZO}/balance", json={"balance": 12345})

    assert _monzo().get_balance("joint") == 12345
    assert balance.last_request.qs == {"account_id": ["acc_joint"]}
    assert balance.last_request.headers["Authorization"] == "Bearer access_token"


def test_get_pot_balance_falls_through_to_business(requests_mock):
    _mock_pots(
        requests_mock,
        personal=[_pot("p1", 100)],
        joint=[_pot("j1", 200)],
        business=[_pot("b1", 300)],
    )
    assert _monzo().get_pot_balance("b1") == 300


def test_get_pot_balance_ignores_deleted_pots(requests_mock):
    _mock_pots(requests_mock, personal=[_pot("p1", 100, deleted=True)])
    with pytest.raises(PotNotFoundError, match="p1"):
        _monzo().get_pot_balance("p1")


def test_get_pot_balance_not_found(requests_mock):
    _mock_pots(requests_mock, personal=[_pot("p1")], joint=[_pot("j1")], business=[_pot("b1")])
    with pytest.raises(PotNotFoundError, match="missing"):
        _monzo().get_pot_balance("missing")


@pytest.mark.parametrize(("pot_id", "expected"), [("p1", "personal"), ("j1", "joint"), ("b1", "business")])
def test_get_account_type(requests_mock, pot_id, expected):
    _mock_pots(requests_mock, personal=[_pot("p1")], joint=[_pot("j1")], business=[_pot("b1")])
    assert _monzo().get_account_type(pot_id) == expected


def test_get_account_type_default_pot_uses_first_pot_found(requests_mock):
    # No personal pots, so the default resolves to the first joint pot.
    _mock_pots(requests_mock, personal=[], joint=[_pot("j1"), _pot("j2")], business=[_pot("b1")])
    assert _monzo().get_account_type("default_pot") == "joint"


def test_get_account_type_not_found(requests_mock):
    _mock_pots(requests_mock, personal=[_pot("p1")], joint=[], business=[_pot("b1")])
    with pytest.raises(PotNotFoundError, match="missing"):
        _monzo().get_account_type("missing")


# --------------------------------------------------------------------------- #
# MonzoAccount deposits / withdrawals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("method", "endpoint", "account_field"),
    [
        ("add_to_pot", "deposit", "source_account_id"),
        ("withdraw_from_pot", "withdraw", "destination_account_id"),
    ],
)
def test_pot_transfer_invalid_selection_falls_back_to_personal(requests_mock, method, endpoint, account_field):
    _mock_pots(requests_mock, personal=[_pot("p1", 1000)])
    transfer = requests_mock.put(f"{MONZO}/pots/p1/{endpoint}", status_code=200)

    getattr(_monzo(), method)("p1", 250, account_selection="nonsense")

    body = parse.parse_qs(transfer.last_request.text)
    assert body[account_field] == ["acc_personal"]
    assert body["amount"] == ["250"]
    assert body["dedupe_id"][0].isdigit()


@pytest.mark.parametrize(
    ("method", "endpoint", "account_field"),
    [
        ("add_to_pot", "deposit", "source_account_id"),
        ("withdraw_from_pot", "withdraw", "destination_account_id"),
    ],
)
def test_pot_transfer_uses_joint_account(requests_mock, method, endpoint, account_field):
    _mock_pots(requests_mock, joint=[_pot("j1", 1000)])
    transfer = requests_mock.put(f"{MONZO}/pots/j1/{endpoint}", status_code=200)

    getattr(_monzo(), method)("j1", 99, account_selection="joint")

    body = parse.parse_qs(transfer.last_request.text)
    assert body[account_field] == ["acc_joint"]
    assert body["amount"] == ["99"]


@pytest.mark.parametrize("method", ["add_to_pot", "withdraw_from_pot"])
def test_pot_transfer_pot_not_found(requests_mock, method):
    _mock_pots(requests_mock, personal=[_pot("other")])
    deposit = requests_mock.put(f"{MONZO}/pots/p1/deposit")
    withdraw = requests_mock.put(f"{MONZO}/pots/p1/withdraw")

    with pytest.raises(PotNotFoundError, match="p1 not found in personal pots"):
        getattr(_monzo(), method)("p1", 100)

    assert not deposit.called
    assert not withdraw.called


@pytest.mark.parametrize("method", ["add_to_pot", "withdraw_from_pot"])
def test_pot_transfer_pot_disappears_on_refetch(requests_mock, method):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    requests_mock.get(
        _pots_url("acc_personal"),
        [{"json": {"pots": [_pot("p1")]}}, {"json": {"pots": [_pot("p1", deleted=True)]}}],
    )
    deposit = requests_mock.put(f"{MONZO}/pots/p1/deposit")
    withdraw = requests_mock.put(f"{MONZO}/pots/p1/withdraw")

    with pytest.raises(PotNotFoundError, match="p1 not found in personal pots"):
        getattr(_monzo(), method)("p1", 100)

    assert not deposit.called
    assert not withdraw.called


@pytest.mark.parametrize(
    ("method", "endpoint", "message"),
    [("add_to_pot", "deposit", "Deposit failed"), ("withdraw_from_pot", "withdraw", "Withdrawal failed")],
)
def test_pot_transfer_non_200_raises(requests_mock, method, endpoint, message):
    _mock_pots(requests_mock, personal=[_pot("p1", 1000)])
    requests_mock.put(
        f"{MONZO}/pots/p1/{endpoint}", status_code=403, json={"code": "forbidden.insufficient_funds"}
    )

    with pytest.raises(PotTransferError, match=message) as excinfo:
        getattr(_monzo(), method)("p1", 100)

    assert "insufficient_funds" in str(excinfo.value)


def test_send_notification_body(requests_mock):
    requests_mock.get(f"{MONZO}/accounts", json=ALL_ACCOUNTS)
    feed = requests_mock.post(f"{MONZO}/feed", status_code=200)

    _monzo().send_notification("Title", "Body text", account_selection="business")

    body = parse.parse_qs(feed.last_request.text)
    assert body["account_id"] == ["acc_business"]
    assert body["type"] == ["basic"]
    assert body["params[title]"] == ["Title"]
    assert body["params[body]"] == ["Body text"]


# --------------------------------------------------------------------------- #
# TrueLayerAccount icons
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("provider_type", "icon"),
    [
        ("American Express", "amex.svg"),
        ("Barclaycard", "barclaycard.svg"),
        ("Halifax", "halifax.svg"),
        ("Lloyds", "lloyds.svg"),
        ("NatWest", "natwest.svg"),
        ("Some Other Bank", "truelayer.svg"),
    ],
)
def test_truelayer_account_icon(provider_type, icon):
    account = TrueLayerAccount(f"{provider_type} 2", provider_type=provider_type)
    assert account.auth_provider.icon_name == icon
    assert account.auth_provider.api_url == "https://api.truelayer.com"


# --------------------------------------------------------------------------- #
# TrueLayerAccount.get_total_balance per provider
# --------------------------------------------------------------------------- #


def _mock_card(requests_mock, card_id, provider, balance, pending=None):
    requests_mock.get(
        f"{TRUELAYER}/cards/{card_id}/balance",
        json={"results": [dict(balance, account_id=card_id)]},
    )
    if pending is not None:
        return requests_mock.get(
            f"{TRUELAYER}/cards/{card_id}/transactions/pending",
            json={"results": [{"amount": a} for a in pending]},
        )
    return None


def _mock_cards(requests_mock, *cards):
    requests_mock.get(
        f"{TRUELAYER}/cards",
        json={"results": [{"account_id": cid, "provider": {"display_name": p}} for cid, p in cards]},
    )


def _truelayer(provider_type="Barclaycard"):
    return TrueLayerAccount(provider_type, "access_token", "refresh_token", time() + 1000)


def test_barclaycard_total_balance_uses_current_and_ignores_pending(requests_mock):
    # Barclaycard is deliberately settled on the reported 'current' balance only:
    # commit 3d7b4b9 switched from `balance = adjusted_balance` to `balance = balance`
    # (an earlier revision noted "barclaycard seem to add pending charges to the
    # balance fairly quickly, so we ignore pending transactions"). Pending
    # transactions are still fetched and logged.
    _mock_cards(requests_mock, ("1", "BARCLAYCARD"))
    pending = _mock_card(requests_mock, "1", "BARCLAYCARD", {"current": 250.25}, pending=[40.50, -10.25])

    assert _truelayer().get_total_balance() == 25025
    assert pending.called


def test_barclaycard_total_balance_without_pending(requests_mock):
    _mock_cards(requests_mock, ("1", "BARCLAYCARD"))
    _mock_card(requests_mock, "1", "BARCLAYCARD", {"current": 99.75}, pending=[])

    assert _truelayer().get_total_balance() == 9975


def test_halifax_total_balance_is_credit_limit_minus_available(requests_mock):
    _mock_cards(requests_mock, ("1", "HALIFAX"))
    pending = requests_mock.get(f"{TRUELAYER}/cards/1/transactions/pending", json={"results": []})
    # 'current' is ignored for Halifax; owed = 1500.00 - 1123.25 = 376.75
    _mock_card(
        requests_mock, "1", "HALIFAX", {"current": 5.00, "credit_limit": 1500.00, "available": 1123.25}
    )

    assert _truelayer("Halifax").get_total_balance() == 37675
    # Halifax has no separate pending feed; it must not be requested.
    assert not pending.called


def test_halifax_total_balance_missing_limit_fields_defaults_to_zero(requests_mock):
    _mock_cards(requests_mock, ("1", "HALIFAX"))
    _mock_card(requests_mock, "1", "HALIFAX", {"current": 42.00})

    assert _truelayer("Halifax").get_total_balance() == 0


def test_lloyds_total_balance_adds_pending_charges(requests_mock):
    _mock_cards(requests_mock, ("1", "LLOYDS"))
    _mock_card(requests_mock, "1", "LLOYDS", {"current": 200.00}, pending=[12.50, 7.25])

    # 200.00 + 12.50 + 7.25 = 219.75
    assert _truelayer("Lloyds").get_total_balance() == 21975


def test_lloyds_total_balance_without_pending(requests_mock):
    _mock_cards(requests_mock, ("1", "LLOYDS"))
    _mock_card(requests_mock, "1", "LLOYDS", {"current": 80.50}, pending=[])

    assert _truelayer("Lloyds").get_total_balance() == 8050


def test_total_balance_sums_mixed_providers(requests_mock):
    _mock_cards(
        requests_mock,
        ("b", "BARCLAYCARD"),
        ("h", "HALIFAX"),
        ("l", "LLOYDS"),
        ("n", "NATWEST"),
    )
    _mock_card(requests_mock, "b", "BARCLAYCARD", {"current": 100.00}, pending=[50.00])
    _mock_card(requests_mock, "h", "HALIFAX", {"credit_limit": 1000.00, "available": 750.00})
    _mock_card(requests_mock, "l", "LLOYDS", {"current": 10.00}, pending=[2.50])
    natwest_pending = requests_mock.get(f"{TRUELAYER}/cards/n/transactions/pending", json={"results": []})
    _mock_card(requests_mock, "n", "NATWEST", {"current": 5.25})

    # 100.00 + 250.00 + 12.50 + 5.25 = 367.75
    assert _truelayer().get_total_balance() == 36775
    assert not natwest_pending.called


def test_total_balance_missing_provider_uses_current(requests_mock):
    requests_mock.get(f"{TRUELAYER}/cards", json={"results": [{"account_id": "1"}]})
    _mock_card(requests_mock, "1", None, {"current": 12.50})

    assert _truelayer().get_total_balance() == 1250


def test_total_balance_is_cached_until_forced(requests_mock):
    _mock_cards(requests_mock, ("1", "LLOYDS"))
    requests_mock.get(
        f"{TRUELAYER}/cards/1/balance",
        [
            {"json": {"results": [{"current": 10.00}]}},
            {"json": {"results": [{"current": 20.00}]}},
        ],
    )
    requests_mock.get(f"{TRUELAYER}/cards/1/transactions/pending", json={"results": []})
    account = _truelayer("Lloyds")

    assert account.get_total_balance() == 1000
    assert account.get_total_balance() == 1000
    assert account.get_total_balance(force_refresh=True) == 2000
