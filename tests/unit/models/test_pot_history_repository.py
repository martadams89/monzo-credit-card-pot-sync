from app.extensions import db
from app.models.pot_history import PotBalanceSnapshotModel, PotMovementModel
from app.models.pot_history_repository import (
    SNAPSHOT_HEARTBEAT_SECONDS,
    SNAPSHOT_RETENTION_DAYS,
    SqlAlchemyPotHistoryRepository,
)

NOW = 1_800_000_000.0


def test_moves_are_listed_newest_first_with_signed_amounts(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_move("American Express", "pot_1", "deposit", 1500, "spending", 1000, 2500, 2500, created_at=NOW - 60)
    repository.record_move("American Express", "pot_1", "withdrawal", 500, "over_funded", 2500, 2000, 2000, created_at=NOW)

    moves = repository.moves()

    assert [m["direction"] for m in moves] == ["withdrawal", "deposit"]
    assert [m["signed_amount"] for m in moves] == [-500, 1500]
    assert moves[0]["reason_label"] == "Pot over card balance"
    assert moves[1]["pot_before"] == 1000 and moves[1]["pot_after"] == 2500


def test_moves_since_and_totals(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_move("Amex", "pot_1", "deposit", 100, "spending", created_at=NOW - 10 * 86400)
    repository.record_move("Amex", "pot_1", "deposit", 200, "spending", created_at=NOW - 60)
    repository.record_move("Amex", "pot_1", "withdrawal", 50, "over_funded", created_at=NOW)

    assert len(repository.moves(since=NOW - 86400)) == 2
    assert repository.totals(since=NOW - 86400) == {"deposited": 200, "withdrawn": 50, "count": 2}
    assert repository.totals() == {"deposited": 300, "withdrawn": 50, "count": 3}


def test_record_move_never_raises(test_client, mocker):
    repository = SqlAlchemyPotHistoryRepository(db)
    mocker.patch.object(repository, "_session", side_effect=RuntimeError("database is locked"))

    repository.record_move("Amex", "pot_1", "deposit", 100, "spending")  # does not raise
    assert repository.record_snapshot("pot_1", "Bills", 100, 100) is False


def test_snapshot_only_written_when_something_changes(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)

    assert repository.record_snapshot("pot_1", "Bills", 1000, 1000, NOW) is True
    assert repository.record_snapshot("pot_1", "Bills", 1000, 1000, NOW + 60) is False
    assert repository.record_snapshot("pot_1", "Bills", 1000, 1200, NOW + 120) is True
    # A heartbeat is written once enough time passes even with no change.
    assert repository.record_snapshot("pot_1", "Bills", 1000, 1200, NOW + 120 + SNAPSHOT_HEARTBEAT_SECONDS) is True

    assert db.session.query(PotBalanceSnapshotModel).count() == 3


def test_unchanged_snapshot_still_picks_up_a_renamed_pot(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_snapshot("pot_1", "Bills", 1000, 1000, NOW)
    repository.record_snapshot("pot_1", "Credit cards", 1000, 1000, NOW + 60)

    assert repository.pot_names() == {"pot_1": "Credit cards"}


def test_old_snapshots_are_pruned(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_snapshot("pot_1", "Bills", 1000, 1000, NOW - (SNAPSHOT_RETENTION_DAYS + 1) * 86400)
    repository.record_snapshot("pot_1", "Bills", 2000, 2000, NOW)

    assert [row.pot_balance for row in db.session.query(PotBalanceSnapshotModel).all()] == [2000]


def test_balance_series_carries_the_last_point_before_the_window(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_snapshot("pot_1", "Bills", 1000, 1000, NOW - 5 * 86400)
    repository.record_snapshot("pot_1", "Bills", 1500, 1500, NOW - 3600)
    repository.record_snapshot("pot_2", "Joint", 300, None, NOW - 10 * 86400)

    since = NOW - 86400
    series = {pot["pot_id"]: pot for pot in repository.balance_series(since)}

    assert series["pot_1"]["points"] == [
        {"t": since, "pot": 1000, "card": 1000},
        {"t": NOW - 3600, "pot": 1500, "card": 1500},
    ]
    # A pot with no change inside the window still shows its last known balance.
    assert series["pot_2"]["points"] == [{"t": since, "pot": 300, "card": None}]
    assert series["pot_2"]["pot_name"] == "Joint"


def test_clear_removes_moves_and_snapshots(test_client):
    repository = SqlAlchemyPotHistoryRepository(db)
    repository.record_move("Amex", "pot_1", "deposit", 100, "spending")
    repository.record_snapshot("pot_1", "Bills", 100, 100)

    assert repository.clear() == 2
    assert db.session.query(PotMovementModel).count() == 0
    assert repository.balance_series(0) == []
