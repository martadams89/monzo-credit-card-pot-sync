from time import time

from app.extensions import db
from app.models.sync_run_repository import SqlAlchemySyncRunRepository


def test_logs_page_empty(test_client):
    response = test_client.get("/logs/")
    assert response.status_code == 200
    assert b"Sync Logs" in response.data
    assert b"No sync runs recorded" in response.data


def test_logs_page_shows_grouped_runs_and_changes(test_client):
    repository = SqlAlchemySyncRunRepository(db)
    now = time()
    repository.record([[now - 600, "INFO", "core", "Card is £10.00"]], now - 600, now - 599)
    repository.record([[now - 480, "INFO", "core", "Card is £10.00"]], now - 480, now - 479)
    repository.record([[now - 120, "ERROR", "core", "Card is <£25.00>"]], now - 120, now - 119)

    response = test_client.get("/logs/")
    assert response.status_code == 200
    assert b"3 sync runs in 2 groups" in response.data
    assert b"&times;2 identical runs" in response.data
    assert b"1 changed line" in response.data
    # Log messages are escaped.
    assert "Card is &lt;£25.00&gt;".encode() in response.data


def test_logs_page_period_filter(test_client):
    repository = SqlAlchemySyncRunRepository(db)
    now = time()
    repository.record([[now - 2 * 86400, "INFO", "core", "two days ago"]], now - 2 * 86400, now - 2 * 86400 + 1)
    repository.record([[now, "INFO", "core", "just now"]], now, now + 1)

    assert b"two days ago" not in test_client.get("/logs/?days=1").data
    assert b"two days ago" in test_client.get("/logs/?days=3").data
    # Unknown periods fall back to the default.
    assert test_client.get("/logs/?days=abc").status_code == 200


def test_nav_links_to_logs(test_client):
    assert b'href="/logs/"' in test_client.get("/").data
