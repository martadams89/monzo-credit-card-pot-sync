"""``SqlAlchemySyncRunRepository.latest()``: the summary shown on the dashboard and /health."""

import pytest

from app.extensions import db
from app.models.sync_run_repository import SqlAlchemySyncRunRepository

NOW = 1_700_000_000.0


def line(message, level="INFO", logger="core", t=NOW):
    return [t, level, logger, message]


@pytest.fixture
def repository(test_client):
    return SqlAlchemySyncRunRepository(db)


def test_latest_is_none_without_runs(repository):
    assert repository.latest() is None


def test_latest_info_run_has_no_problem(repository):
    repository.record([line("Pot is £10.00"), line("Done")], NOW, NOW + 3)

    assert repository.latest() == {
        "last_started_at": NOW,
        "finished_at": NOW + 3,
        "level": "INFO",
        "repeat_count": 1,
        "problem": None,
    }


def test_latest_reflects_collapsed_repeats(repository):
    repository.record([line("Same")], NOW, NOW + 1)
    repository.record([line("Same")], NOW + 120, NOW + 121)

    latest = repository.latest()

    assert latest["repeat_count"] == 2
    assert latest["last_started_at"] == NOW + 120
    assert latest["finished_at"] == NOW + 121


def test_latest_returns_the_most_recent_run(repository):
    repository.record([line("First", "ERROR")], NOW, NOW + 1)
    repository.record([line("Second")], NOW + 120, NOW + 121)

    latest = repository.latest()

    assert latest["level"] == "INFO"
    assert latest["problem"] is None
    assert latest["finished_at"] == NOW + 121


def test_problem_is_the_last_message_at_the_run_level(repository):
    repository.record(
        [
            line("Starting"),
            line("Card is slow", "WARNING"),
            line("First failure", "ERROR"),
            line("Another warning", "WARNING"),
            line("Second failure", "ERROR"),
            line("Finished"),
        ],
        NOW,
        NOW + 1,
    )

    latest = repository.latest()

    assert latest["level"] == "ERROR"
    assert latest["problem"] == "Second failure"


def test_warning_run_reports_its_warning(repository):
    repository.record([line("Starting"), line("Reconnect soon", "WARNING"), line("Done")], NOW, NOW + 1)

    latest = repository.latest()

    assert latest["level"] == "WARNING"
    assert latest["problem"] == "Reconnect soon"


def test_problem_keeps_only_the_first_line_of_a_traceback(repository):
    repository.record(
        [line("Sync run failed\nTraceback (most recent call last):\n  File ...", "ERROR")], NOW, NOW + 1
    )

    assert repository.latest()["problem"] == "Sync run failed"


def test_empty_run_is_info_with_no_problem(repository):
    repository.record([], NOW, NOW + 1)

    latest = repository.latest()

    assert latest["level"] == "INFO"
    assert latest["problem"] is None


def test_empty_problem_message_is_none(repository):
    repository.record([line("", "ERROR")], NOW, NOW + 1)

    latest = repository.latest()

    assert latest["level"] == "ERROR"
    assert latest["problem"] is None
