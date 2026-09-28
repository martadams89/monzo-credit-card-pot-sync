import logging
import threading

import pytest

from app.domain.settings import Setting
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.sync_run import SyncRunModel
from app.models.sync_run_repository import SqlAlchemySyncRunRepository
from app.utils.sync_log import record_sync_run

NOW = 1_700_000_000.0


def line(message, level="INFO", logger="core", t=NOW):
    return [t, level, logger, message]


@pytest.fixture
def repository(test_client):
    return SqlAlchemySyncRunRepository(db)


def test_identical_consecutive_runs_are_collapsed(repository):
    repository.record([line("Pot is £10.00", t=NOW)], NOW, NOW + 1)
    repository.record([line("Pot is £10.00", t=NOW + 120)], NOW + 120, NOW + 121)
    repository.record([line("Pot is £10.00", t=NOW + 240)], NOW + 240, NOW + 241)

    runs = db.session.query(SyncRunModel).all()
    assert len(runs) == 1
    assert runs[0].repeat_count == 3
    assert runs[0].started_at == NOW
    assert runs[0].last_started_at == NOW + 240
    assert runs[0].finished_at == NOW + 241


def test_a_change_starts_a_new_group_and_is_highlighted(repository):
    repository.record([line("Pot is £10.00"), line("Card is £10.00")], NOW, NOW + 1)
    repository.record([line("Pot is £10.00"), line("Card is £10.00")], NOW + 120, NOW + 121)
    repository.record([line("Pot is £10.00"), line("Card is £25.00")], NOW + 240, NOW + 241)
    # Going back to an earlier output is still a change from the run just before.
    repository.record([line("Pot is £10.00"), line("Card is £10.00")], NOW + 360, NOW + 361)

    runs = repository.list_since(0)
    assert [r["repeat_count"] for r in runs] == [1, 1, 2]
    newest, middle, oldest = runs
    assert [ln["changed"] for ln in newest["lines"]] == [False, True]
    assert [ln["changed"] for ln in middle["lines"]] == [False, True]
    assert middle["changed_count"] == 1
    assert middle["removed_count"] == 1
    assert oldest["is_first"] is True
    assert oldest["changed_count"] == 0


def test_oldest_group_in_window_is_diffed_against_the_run_before_it(repository):
    repository.record([line("Card is £10.00")], NOW, NOW + 1)
    repository.record([line("Card is £25.00")], NOW + 86400, NOW + 86401)

    runs = repository.list_since(NOW + 3600)
    assert len(runs) == 1
    assert runs[0]["is_first"] is False
    assert runs[0]["lines"][0]["changed"] is True


def test_list_is_limited_and_still_diffs_the_oldest_shown(repository):
    for i in range(5):
        repository.record([line(f"Card is £{i}.00")], NOW + i * 120, NOW + i * 120 + 1)

    runs = repository.list_since(0, limit=2)
    assert [r["lines"][0]["message"] for r in runs] == ["Card is £4.00", "Card is £3.00"]
    assert runs[-1]["is_first"] is False
    assert runs[-1]["changed_count"] == 1


def test_run_level_is_the_highest_logged(repository):
    repository.record([line("ok"), line("careful", "WARNING"), line("ok again")], NOW, NOW + 1)
    assert db.session.query(SyncRunModel).one().level == "WARNING"


def test_old_runs_are_pruned_using_the_retention_setting(repository):
    SqlAlchemySettingRepository(db).save(Setting("log_retention_days", "2"))
    repository.record([line("old")], NOW, NOW + 1)
    repository.record([line("recent")], NOW + 86400, NOW + 86401)
    repository.record([line("now")], NOW + 3 * 86400, NOW + 3 * 86400 + 1)

    messages = [r["lines"][0]["message"] for r in repository.list_since(0)]
    assert messages == ["now", "recent"]


def test_invalid_retention_setting_falls_back_to_default(repository):
    SqlAlchemySettingRepository(db).save(Setting("log_retention_days", "abc"))
    repository.record([line("old")], NOW, NOW + 1)
    repository.record([line("new")], NOW + 6 * 86400, NOW + 6 * 86400 + 1)
    assert len(repository.list_since(0)) == 2


def test_record_sync_run_captures_only_this_threads_logs(repository, caplog):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("core")

    def other_thread():
        logging.getLogger("web").info("request from another thread")

    with record_sync_run(repository):
        logger.info("Pot is £10.00")
        t = threading.Thread(target=other_thread)
        t.start()
        t.join()
        logger.warning("Something odd")

    run = repository.list_since(0)[0]
    assert [(ln["level"], ln["logger"], ln["message"]) for ln in run["lines"]] == [
        ("INFO", "core", "Pot is £10.00"),
        ("WARNING", "core", "Something odd"),
    ]


def test_record_sync_run_records_and_reraises_failures(repository, caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(RuntimeError), record_sync_run(repository):
        logging.getLogger("core").info("Starting")
        raise RuntimeError("boom")

    run = repository.list_since(0)[0]
    assert run["level"] == "ERROR"
    assert "RuntimeError: boom" in run["lines"][-1]["message"]


def test_record_sync_run_survives_a_failure_to_save(mocker):
    repository = mocker.Mock()
    repository.record.side_effect = Exception("database locked")
    with record_sync_run(repository):
        logging.getLogger("core").info("Still syncs")
    repository.record.assert_called_once()


def test_lines_that_disappear_are_counted(repository):
    repository.record([line("ok"), line("Provider unavailable", "WARNING")], NOW, NOW + 1)
    repository.record([line("ok")], NOW + 120, NOW + 121)

    newest = repository.list_since(0)[0]
    assert newest["changed_count"] == 0
    assert newest["removed_count"] == 1


def test_record_sync_run_caps_lines_per_run(repository, caplog, mocker):
    caplog.set_level(logging.INFO)
    mocker.patch("app.utils.sync_log.MAX_LINES_PER_RUN", 3)
    with record_sync_run(repository):
        for i in range(5):
            logging.getLogger("core").info(f"line {i}")

    lines = [ln["message"] for ln in repository.list_since(0)[0]["lines"]]
    assert lines == ["line 0", "line 1", "line 2", "2 further log line(s) not recorded"]


def test_record_sync_run_survives_a_malformed_log_call(repository, caplog, mocker):
    caplog.set_level(logging.INFO)
    mocker.patch.object(logging, "raiseExceptions", False)
    with record_sync_run(repository):
        logging.getLogger("core").info("%d pots", "not a number")
        logging.getLogger("core").info("still recorded")

    lines = [ln["message"] for ln in repository.list_since(0)[0]["lines"]]
    assert lines == ["still recorded"]
