from app import create_app
from app.config import Config


def test_create_app_schedules_the_sync_at_the_configured_interval(tmp_path, monkeypatch, mocker):
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'app.db'}")
    scheduler = mocker.patch("app.extensions.scheduler")

    app = create_app()

    assert app.config["TESTING"] is False
    scheduler.init_app.assert_called_once_with(app)
    scheduler.add_job.assert_called_once()
    kwargs = scheduler.add_job.call_args.kwargs
    assert kwargs["id"] == "sync_balance"
    assert kwargs["trigger"] == "interval"
    assert kwargs["seconds"] == 120
    scheduler.start.assert_called_once()
    assert "logs" in app.blueprints
