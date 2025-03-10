from app.core import sync_balance

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
    feed_mock = requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)

    # Add a mock for pot deposit
    deposit_mock = requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)

    ### When ###
    sync_balance()

    ### Then ###
    # Verify no deposit was made since balances match
    assert not deposit_mock.called, "No deposit should be made when balances match"
    # Verify feed notification was sent
    assert feed_mock.called, "Feed notification should be sent"

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
    deposit_mock = requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)

    ### When ###
    sync_balance()

    ### Then ###
    # Verify deposit was made to cover the difference
    assert deposit_mock.called, "Deposit should be made to match credit card balance"
    # Check deposit amount (should be difference between 1000 and 10 = 990)
    assert "amount=99000" in deposit_mock.last_request.text

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
    withdraw_mock = requests_mock.put("https://api.monzo.com/pots/pot_id/withdraw", json={"status": "ok"}, status_code=200)

    # Add a mock for feed notification
    feed_mock = requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)

    ### When ###
    sync_balance()

    ### Then ###
    # Verify withdrawal was made
    assert withdraw_mock.called, "Withdrawal should be made when pot balance exceeds credit card balance"
    # Check withdrawal amount (should be difference between 10 and 9 = 1)
    assert "amount=100" in withdraw_mock.last_request.text
    # Verify feed notification was sent
    assert feed_mock.called, "Feed notification should be sent"

# Implement the commented-out test for insufficient account balance
def test_core_flow_insufficient_account_balance(mocker, test_client, requests_mock, seed_data):
    ### Given ###
    mocker.patch("app.core.scheduler")
    mock_logger = mocker.patch("app.core.log")

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

    # Mock Monzo account balance with insufficient funds
    requests_mock.get(
        "https://api.monzo.com/accounts",
        json={"accounts": [{"id": "acc_id", "type": "uk_retail", "currency": "GBP"}]},
    )
    requests_mock.get(
        "https://api.monzo.com/balance?account_id=acc_id", json={"balance": 5000}  # Only £50 available
    )

    # Mock pot deposit call - shouldn't be called due to insufficient funds
    deposit_mock = requests_mock.put("https://api.monzo.com/pots/pot_id/deposit", json={"status": "ok"}, status_code=200)
    
    # Mock feed notification
    feed_mock = requests_mock.post("https://api.monzo.com/feed", json={}, status_code=200)

    ### When ###
    sync_balance()

    ### Then ###
    # Verify no deposit was attempted due to insufficient funds
    assert not deposit_mock.called, "No deposit should be made when account has insufficient funds"
    # Verify error was logged
    mock_logger.error.assert_called_with(mocker.ANY, extra=mocker.ANY)
    # Verify feed notification was sent with warning
    assert feed_mock.called, "Feed notification should be sent with insufficient funds warning"