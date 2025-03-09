"""Utility for managing database migrations at application startup."""

import os
import logging
from flask import current_app
from flask_migrate import Migrate, upgrade
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

def check_and_apply_migrations(app, db):
    """Check if database exists and is up to date with migrations.
    
    This function:
    1. Checks if the database exists, creates it if not
    2. Creates tables if they don't exist
    3. Applies any pending migrations
    
    Args:
        app: Flask application instance
        db: SQLAlchemy instance
        
    Returns:
        bool: True if database is ready, False if there were errors
    """
    try:
        logger.info("Checking database status...")
        
        # Check if database exists and create if needed
        if ensure_database_exists(app, db):
            logger.info("Database exists or was created successfully.")
        else:
            logger.error("Failed to create or access database.")
            return False
        
        # Check if tables exist and create if needed
        if ensure_tables_exist(app, db):
            logger.info("Database tables exist or were created successfully.")
        else:
            logger.error("Failed to create database tables.")
            return False
        
        # Apply migrations
        if apply_migrations(app, db):
            logger.info("Database migrations applied successfully.")
        else:
            logger.warning("Failed to apply some migrations.")
            # Continue anyway as the database might still be usable
        
        return True
        
    except Exception as e:
        logger.exception(f"Error during database migration check: {str(e)}")
        return False

def ensure_database_exists(app, db):
    """Ensure the SQLite database exists."""
    try:
        # Try to connect to the database
        engine = db.engine
        connection = engine.connect()
        connection.close()
        return True
    except OperationalError:
        # Database doesn't exist, create its directory
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if not db_path:  # In-memory SQLite
            return True
            
        # Create directory for SQLite database file
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        return True

def ensure_tables_exist(app, db):
    """Ensure database tables exist."""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        # Check if key tables exist
        required_tables = ['users', 'accounts', 'sync_records', 'settings']
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.info(f"Missing tables: {', '.join(missing_tables)}")
            logger.info("Creating all tables...")
            db.create_all()
            return True
        else:
            logger.info("All required tables exist.")
            return True
            
    except Exception as e:
        logger.exception(f"Error checking/creating tables: {str(e)}")
        return False

def apply_migrations(app, db):
    """Apply any pending migrations."""
    try:
        # Initialize Flask-Migrate
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'migrations')
        migrate = Migrate(app, db, directory=migrations_dir)
        
        # Check if we have any pending migrations
        with app.app_context():
            conn = db.engine.connect()
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            logger.info(f"Current migration revision: {current_rev or 'None'}")
            
            # Try to apply migrations, handling the multiple heads case
            try:
                # First try normal upgrade
                upgrade(directory=migrations_dir)
            except Exception as e:
                if "Multiple head revisions are present" in str(e):
                    # Handle multiple heads by using 'heads' instead of 'head'
                    logger.warning("Multiple migration heads detected. Attempting to apply all heads.")
                    try:
                        upgrade(directory=migrations_dir, revision='heads')
                    except Exception as e2:
                        logger.error(f"Error applying multiple heads: {str(e2)}")
                        return False
                else:
                    logger.error(f"Error during migration: {str(e)}")
                    return False
            
            # Get new revision
            context = MigrationContext.configure(conn)
            new_rev = context.get_current_revision()
            logger.info(f"New migration revision: {new_rev or 'None'}")
            
            conn.close()
            
        return True
    except Exception as e:
        logger.exception(f"Error applying migrations: {str(e)}")
        return False
