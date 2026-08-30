import logging

from sqlalchemy import inspect, text

log = logging.getLogger("migrations")


def migrate_database(db) -> None:
    """Apply the small, backwards-compatible schema changes used by the app.

    The project predates a migration framework and existing deployments use a
    persistent SQLite volume. ``create_all`` creates fresh databases but does
    not add columns to an existing table, so add the provider column in place
    and populate it from the legacy account name.
    """
    db.create_all()

    inspector = inspect(db.engine)
    if "account_model" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("account_model")}
    if "provider" not in columns:
        log.info("Adding provider metadata to existing account connections")
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE account_model ADD COLUMN provider VARCHAR(50)")
            )

    # Also repairs a partially-completed migration without changing any
    # connection names, tokens, pot mappings, or balance state.
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE account_model SET provider = type "
                "WHERE provider IS NULL OR provider = ''"
            )
        )
