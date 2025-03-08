"""Database migration utilities"""

import logging
from flask import current_app
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from app.models.user import User
from app.models.setting import Setting
from app.models.cooldown import Cooldown

log = logging.getLogger("db_migrations")

# Store migration functions 
# Each function takes the db connection and performs a migration step
MIGRATIONS = []

def migration(func):
    """Decorator to register a migration function"""
    MIGRATIONS.append(func)
    return func

@migration
def create_setting_version_table(db):
    """Create the db_version table if it doesn't exist"""
    try:
        db.session.execute("""
            CREATE TABLE IF NOT EXISTS db_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if we have a version row, if not create it
        version = db.session.execute("SELECT version FROM db_version").fetchone()
        if not version:
            db.session.execute("INSERT INTO db_version (version) VALUES (0)")
        
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        log.error(f"Error creating version table: {e}")
        return False

@migration
def add_security_fields_to_user(db):
    """Add security-related fields to User table"""
    try:
        # Check if the columns exist before trying to add them
        inspector = sa.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        # Only add columns that don't exist
        columns_to_add = []
        
        if 'email_verified' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0")
        
        if 'email_verification_token' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN email_verification_token TEXT")
        
        if 'email_verification_expiry' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN email_verification_expiry TIMESTAMP")
        
        if 'totp_secret' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN totp_secret TEXT")
        
        if 'totp_enabled' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN totp_enabled BOOLEAN DEFAULT 0")
        
        if 'backup_codes' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN backup_codes TEXT")
        
        if 'passkeys' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN passkeys TEXT DEFAULT '[]'")
        
        if 'preferences' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN preferences TEXT DEFAULT '{}'")
        
        if 'last_login_at' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN last_login_at TIMESTAMP")
        
        if 'last_login_ip' not in columns:
            columns_to_add.append("ALTER TABLE user ADD COLUMN last_login_ip TEXT")
        
        # Execute all alter table statements
        for statement in columns_to_add:
            try:
                db.session.execute(statement)
            except OperationalError as e:
                # If column already exists, SQLite will raise an error
                log.warning(f"Column already exists: {e}")
        
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        log.error(f"Error adding security fields: {e}")
        return False

def get_current_db_version(db):
    """Get the current database version"""
    try:
        # Check if version table exists
        inspector = sa.inspect(db.engine)
        if 'db_version' not in inspector.get_table_names():
            return 0
            
        version = db.session.execute("SELECT version FROM db_version").fetchone()
        return version[0] if version else 0
    except SQLAlchemyError as e:
        log.error(f"Error getting db version: {e}")
        return 0

def update_db_version(db, new_version):
    """Update the database version"""
    try:
        db.session.execute("UPDATE db_version SET version = :version", {"version": new_version})
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        log.error(f"Error updating db version: {e}")
        return False

def run_migrations(db):
    """Run all pending migrations"""
    log.info("Running database migrations...")
    
    # Create version table if it doesn't exist
    create_setting_version_table(db)
    
    current_version = get_current_db_version(db)
    target_version = len(MIGRATIONS)
    
    log.info(f"Current DB version: {current_version}, Target version: {target_version}")
    
    if current_version >= target_version:
        log.info("Database is up to date")
        return True
    
    success = True
    for i in range(current_version, target_version):
        migration_func = MIGRATIONS[i]
        log.info(f"Running migration {i+1}: {migration_func.__name__}")
        
        if migration_func(db):
            log.info(f"Migration {i+1} completed successfully")
        else:
            log.error(f"Migration {i+1} failed")
            success = False
            break
    
    if success:
        update_db_version(db, target_version)
        log.info(f"Migrations completed successfully. New db version: {target_version}")
    
    return success
