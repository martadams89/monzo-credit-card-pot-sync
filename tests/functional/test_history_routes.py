from time import time

from app import sync_status
from app.extensions import db
from app.models.pot_history_repository import SqlAlchemyPotHistoryRepository


def test_history_page_empty(test_client):
    response = test_client.get("/history/")
    assert response.status_code == 200
    assert b"No moves in this period" in response.data
    assert b"pot_chart.js" in response.data


def test_history_page_lists_moves_with_pot_names(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    now = time()
    repository.record_snapshot("pot_1", "Old name", 2500, 2500, now - 120)
    sync_status.save([{"type": "American Express", "pot_id": "pot_1", "pot_name": "Credit <cards>"}], now)
    repository.record_move("American Express", "pot_1", "deposit", 1500, "spending", 1000, 2500, 2500, created_at=now - 60)
    repository.record_move("American Express", "pot_1", "withdrawal", 250, "over_funded", 2500, 2250, 2250, created_at=now)

    response = test_client.get("/history/")
    body = response.data.decode()

    assert "Deposited into Credit &lt;cards&gt;" in body
    assert "Withdrew from Credit &lt;cards&gt;" in body
    assert "Card spending" in body and "Pot over card balance" in body
    assert "£15.00" in body and "£2.50" in body
    # The chart data is embedded as JSON.
    assert '"pot_id": "pot_1"' in body


def test_history_period_filter(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    now = time()
    repository.record_move("Amex", "pot_1", "deposit", 111, "spending", created_at=now - 40 * 86400)

    assert "£1.11" not in test_client.get("/history/").data.decode()
    assert "£1.11" in test_client.get("/history/?days=90").data.decode()
    assert test_client.get("/history/?days=nope").status_code == 200


def test_history_clear(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_move("Amex", "pot_1", "deposit", 100, "spending")

    response = test_client.post("/history/clear", follow_redirects=True)

    assert b"History cleared (1 entry)" in response.data
    assert repository.moves() == []


def test_nav_links_to_history(test_client):
    assert b'href="/history/"' in test_client.get("/").data
