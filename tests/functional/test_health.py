"""GET /health: whether the sync loop is alive, for Docker or an uptime monitor."""

from time import time

import pytest

from app.domain.settings import Setting
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.sync_run_repository import SqlAlchemySyncRunRepository


def _save_setting(key, value):
    SqlAlchemySettingRepository(db).save(Setting(key, value))


def _record_run(age_seconds, level="INFO", message="All credit accounts processed."):
    finished_at = time() - age_seconds
    SqlAlchemySyncRunRepository(db).record([[finished_at, level, "core", message]], finished_at - 2, finished_at)


def test_starting_when_no_sync_has_run(test_client):
    response = test_client.get("/health")

    assert response.status_code == 503
    assert response.json == {"status": "starting", "detail": "No sync has run yet"}


def test_ok_after_a_recent_sync(test_client):
    _record_run(10)

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["last_sync_level"] == "INFO"
    assert 9 <= response.json["last_sync_seconds_ago"] <= 12


def test_a_run_that_logged_an_error_is_still_healthy(test_client):
    _record_run(10, level="ERROR", message="Monzo is down")

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["last_sync_level"] == "ERROR"


@pytest.mark.parametrize(
    ("interval", "max_age"),
    [
        (120, 360),  # 3 intervals
        (60, 300),  # but never less than five minutes
        (1, 300),
        (600, 1800),
    ],
)
def test_stale_after_three_intervals_with_a_five_minute_minimum(test_client, interval, max_age):
    _save_setting("sync_interval_seconds", str(interval))

    _record_run(max_age - 20)
    fresh = test_client.get("/health")
    assert fresh.status_code == 200
    assert fresh.json["status"] == "ok"

    _record_run(max_age + 20, message="an older, different run")
    stale = test_client.get("/health")
    # The latest run is the one recorded last, whatever its timestamp.
    assert stale.status_code == 503
    assert stale.json["status"] == "stale"
    assert stale.json["last_sync_level"] == "INFO"
    assert max_age + 19 <= stale.json["last_sync_seconds_ago"] <= max_age + 22


@pytest.mark.parametrize("bad", ["not-a-number", "", "12.5"])
def test_bad_interval_setting_falls_back_to_two_minutes(test_client, bad):
    _save_setting("sync_interval_seconds", bad)

    _record_run(340)
    assert test_client.get("/health").status_code == 200

    _record_run(380, message="different")
    assert test_client.get("/health").status_code == 503


def test_missing_interval_setting_uses_default(test_client):
    from app.models.setting import SettingModel

    SettingModel.query.filter_by(key="sync_interval_seconds").delete()
    db.session.commit()

    _record_run(340)
    assert test_client.get("/health").status_code == 200
    _record_run(380, message="different")
    assert test_client.get("/health").status_code == 503


def test_health_does_not_need_sign_in(test_client, mocker):
    # Monitors can't sign in; the endpoint stays reachable when login is on.
    mocker.patch("app.security.auth_required", return_value=True)
    _record_run(10)
    assert test_client.get("/").status_code == 302  # other pages do need it

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
