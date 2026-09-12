from time import time
from urllib.parse import parse_qs

from app.core import sync_balance
from app.domain.auth_providers import AuthProviderType
from app.extensions import db
from app.models.account import AccountModel


def test_core_flow_successful_no_change_required(mocker, test_client, requests_mock, seed_data):
    ### Given ###
    mocker.patch("app.core.scheduler")

    # Mock ping calls for seeded accounts
    requests_mock.get("https://api.monzo.com/ping/whoami")
    requests_mock.get("https://api.truelayer.com/data/v1/me")

    # Mock pot balance call, returning 1000p (£10)
    requests_mock.get(
        "https://api.monzo.com/pots",
        json={"pots": [{"id": "pot_id", "balance": 1000, "deleted": False}]},
    )

    # Mock credit account balance calls, returning £10
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance",
        json={"results": [{"current": 10}]},
    )

    # Updated: Mock Monzo account balance call with "type" and "currency"
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": 100}
    )

    # Add a mock for feed notification
    requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)

    # Add a mock for pot deposit
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)

    ### When ###
    sync_balance()


def test_core_flow_successful_deposit(mocker, test_client, requests_mock, seed_data):
    ### Given ###
    mocker.patch("app.core.scheduler")

    # Mock ping calls for seeded accounts
    requests_mock.get("https://api.monzo.com/ping/whoami")
    requests_mock.get("https://api.truelayer.com/data/v1/me")

    # Mock pot balance call, returning 1000p (£10)
    requests_mock.get(
        "https://api.monzo.com/pots",
        json={"pots": [{"id": "pot_id", "balance": 1000, "deleted": False}]},
    )

    # Mock credit account balance calls, returning £1000
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance",
        json={"results": [{"current": 1000}]},
    )

    # Updated: Mock Monzo account balance call with required fields
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": 100000}
    )

    # Mock pot deposit call
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit")
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)

    ### When ###
    sync_balance()


def test_core_flow_successful_withdrawal(mocker, test_client, requests_mock, seed_data):
    ### Given ###
    mocker.patch("app.core.scheduler")

    # Mock ping calls for seeded accounts
    requests_mock.get("https://api.monzo.com/ping/whoami")
    requests_mock.get("https://api.truelayer.com/data/v1/me")

    # Mock pot balance call, returning 1000p (£10)
    requests_mock.get(
        "https://api.monzo.com/pots",
        json={"pots": [{"id": "pot_id", "balance": 1000, "deleted": False}]},
    )

    # Mock credit account balance calls, returning £9 (i.e., 9p)
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance",
        json={"results": [{"current": 9}]},
    )

    # Updated: Mock Monzo account balance call with fields
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": 100}
    )

    # Mock pot withdrawal call
    requests_mock.put("https://api.monzo.com/pots/pot_id/withdraw")
    requests_mock.put("https://api.monzo.com/pots/pot_id/withdraw", json={"status": "ok"}, status_code=200)

    # Add a mock for feed notification
    requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)

    # Add a mock for pot deposit
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)

    ### When ###
    sync_balance()


# def test_core_flow_insufficient_account_balance(mocker, test_client, requests_mock, seed_data):
#     ### Given ###
#     mocker.patch("app.core.scheduler")

#     # Mock ping calls for seeded accounts
#     requests_mock.get("https://api.monzo.com/ping/whoami")
#     requests_mock.get("https://api.truelayer.com/data/v1/me")

#     # Mock pot balance call, returning 1000p (£10)
#     requests_mock.get(
#         "https://api.monzo.com/pots",
#         json={"pots": [{"id": "pot_id", "balance": 1000, "deleted": False}]},
#     )

#     # Mock credit account balance calls, returning £1000
#     requests_mock.get(
#         "https://api.truelayer.com/data/v1/cards",
#         json={"results": [{"account_id": "card_id"}]},
#     )
#     requests_mock.get(
#         "https://api.truelayer.com/data/v1/cards/card_id/balance",
#         json={"results": [{"current": 1000}]},
#     )

#     # Updated: Mock Monzo account balance call with additional account details
#     requests_mock.get(
#         "https://api.monzo.com/accounts",
#         json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
#     )
#     requests_mock.get(
#         "https://api.monzo.com/balance?account_id=acc_id", json={"balance": 50000}
#     )

#     # Mock a post to the feed for insufficient funds notification
#     requests_mock.post("https://api.monzo.com/feed")

#     ### When ###
#     sync_balance()

class _Pot:
    """A pot whose balance moves with the transfers the sync makes against it.

    The sync re-reads the pot after every transfer, so a fixed balance would make the
    later steps of a run see a pot that was never topped up or emptied.
    """

    def __init__(self, balance):
        self.balance = balance
        self.deposits = []
        self.withdrawals = []

    def deposit(self, request, context):
        amount = int(parse_qs(request.text)["amount"][0])
        self.deposits.append(amount)
        self.balance += amount
        return {"status": "ok"}

    def withdraw(self, request, context):
        amount = int(parse_qs(request.text)["amount"][0])
        self.withdrawals.append(amount)
        self.balance -= amount
        return {"status": "ok"}


def _mock_sync_endpoints(requests_mock, *, pot_balance, card_balance, monzo_balance=1000000):
    """Wire up the Monzo and TrueLayer calls a single sync run makes.

    ``pot_balance`` is in pence to match the Monzo API; ``card_balance`` is in pounds
    to match TrueLayer.
    """
    pot = _Pot(pot_balance)

    requests_mock.get("https://api.monzo.com/ping/whoami")
    requests_mock.get("https://api.truelayer.com/data/v1/me")
    requests_mock.get(
        "https://api.monzo.com/pots",
        json=lambda request, context: {
            "pots": [{"id": "pot_id", "balance": pot.balance, "deleted": False}]
        },
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards",
        json={"results": [{"account_id": "card_id"}]},
    )
    requests_mock.get(
        "https://api.truelayer.com/data/v1/cards/card_id/balance",
        json={"results": [{"current": card_balance}]},
    )
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": monzo_balance}
    )
    requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)
    requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json=pot.deposit)
    requests_mock.put("https://api.monzo.com/pots/pot_id/withdraw", json=pot.withdraw)
    return pot


def _set_cooldown(account_type, **fields):
    record = AccountModel.query.filter_by(type=account_type).one()
    for field, value in fields.items():
        setattr(record, field, value)
    db.session.commit()


def test_active_cooldown_holds_while_pot_is_short_of_card(
    mocker, test_client, requests_mock, seed_data
):
    """A pot raided to pay the card must not be refilled while the payment is pending.

    The card still shows £1963.27 because the payment has not cleared, so the pot
    sitting £29.27 below it is the payment in flight, not new spending.
    """
    ### Given ###
    mocker.patch("app.core.scheduler")
    cooldown_until = int(time()) + 3 * 3600
    _set_cooldown(
        AuthProviderType.AMEX.value,
        prev_balance=196327,
        cooldown_until=cooldown_until,
        cooldown_ref_card_balance=196327,
    )
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until == cooldown_until
    assert account.prev_balance == 196327
    assert pot.deposits == []
    assert pot.withdrawals == []


def test_pot_is_not_refilled_on_the_run_after_a_cooldown_starts(
    mocker, test_client, requests_mock, seed_data
):
    """The reported failure, end to end: pay the card from the pot, then sync twice.

    The first run opens a cooldown because the pot dropped without the card moving.
    The second run, two minutes later with nothing else changed, has to leave both
    alone - it used to end the cooldown and pull the shortfall out of the account.
    """
    ### Given ###
    mocker.patch("app.core.scheduler")
    _set_cooldown(AuthProviderType.AMEX.value, prev_balance=196327)
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    ### When ###
    sync_balance()
    cooldown_until = (
        AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one().cooldown_until
    )
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until == cooldown_until
    assert account.cooldown_ref_card_balance == 196327
    assert account.prev_balance == 196327
    assert pot.deposits == []
    assert pot.withdrawals == []
    assert pot.balance == 193400


def test_stale_zero_cooldown_reference_does_not_end_cooldown(
    mocker, test_client, requests_mock, seed_data
):
    """A 0 reference left by the old column default must not be read as a baseline.

    A cooldown only starts while the card is above the pot, so 0 is never a card
    balance a cooldown was opened against.
    """
    ### Given ###
    mocker.patch("app.core.scheduler")
    cooldown_until = int(time()) + 3 * 3600
    _set_cooldown(
        AuthProviderType.AMEX.value,
        prev_balance=4498,
        cooldown_until=cooldown_until,
        cooldown_ref_card_balance=0,
    )
    pot = _mock_sync_endpoints(requests_mock, pot_balance=0, card_balance=44.98)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until == cooldown_until
    assert account.prev_balance == 4498
    assert pot.deposits == []
    assert pot.withdrawals == []


def test_cooldown_ends_and_pot_is_reconciled_once_payment_clears(
    mocker, test_client, requests_mock, seed_data
):
    """Once the card comes down to meet the pot the cooldown ends and the pot is emptied."""
    ### Given ###
    mocker.patch("app.core.scheduler")
    _set_cooldown(
        AuthProviderType.AMEX.value,
        prev_balance=196327,
        cooldown_until=int(time()) + 3 * 3600,
        cooldown_ref_card_balance=196327,
    )
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=29.27)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until is None
    assert account.cooldown_ref_card_balance is None
    assert account.prev_balance == 2927
    assert pot.deposits == []
    assert pot.withdrawals == [190473]
    assert pot.balance == 2927


def test_expired_cooldown_does_not_deposit_against_a_settled_card(
    mocker, test_client, requests_mock, seed_data
):
    """At expiry the shortfall is measured against the live card, not the old balance."""
    ### Given ###
    mocker.patch("app.core.scheduler")
    _set_cooldown(
        AuthProviderType.AMEX.value,
        prev_balance=196327,
        cooldown_until=int(time()) - 60,
        cooldown_ref_card_balance=196327,
    )
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=29.27)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until is None
    assert account.cooldown_ref_card_balance is None
    assert pot.deposits == []
    assert pot.withdrawals == [190473]


def test_expired_cooldown_tops_the_pot_back_up_when_the_card_still_owes(
    mocker, test_client, requests_mock, seed_data
):
    """If the card never came down, the pot is topped back up to it when the cooldown ends."""
    ### Given ###
    mocker.patch("app.core.scheduler")
    _set_cooldown(
        AuthProviderType.AMEX.value,
        prev_balance=196327,
        cooldown_until=int(time()) - 60,
        cooldown_ref_card_balance=196327,
    )
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until is None
    assert account.cooldown_ref_card_balance is None
    assert account.prev_balance == 196327
    assert pot.deposits == [2927]
    assert pot.withdrawals == []
    assert pot.balance == 196327


def test_new_cooldown_records_the_card_balance_it_was_opened_against(
    mocker, test_client, requests_mock, seed_data
):
    """The reference balance has to be persisted, or the next run has nothing to compare."""
    ### Given ###
    mocker.patch("app.core.scheduler")
    _set_cooldown(AuthProviderType.AMEX.value, prev_balance=196327)
    pot = _mock_sync_endpoints(requests_mock, pot_balance=193400, card_balance=1963.27)

    ### When ###
    sync_balance()

    ### Then ###
    account = AccountModel.query.filter_by(type=AuthProviderType.AMEX.value).one()
    assert account.cooldown_until is not None
    assert account.cooldown_until > int(time())
    assert account.cooldown_ref_card_balance == 196327
    assert account.prev_balance == 196327
    assert pot.deposits == []
    assert pot.withdrawals == []
