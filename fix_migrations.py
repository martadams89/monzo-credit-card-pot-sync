#!/usr/bin/env python
"""Script to fix database migration issues by merging multiple heads."""

import os
import sys
import shutil
from datetime import datetime
import tempfile
import sqlite3
import subprocess

def reset_migrations_folder():
    """Clean the migrations folder and create a new initial migration."""
    print("Cleaning migrations directory...")
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    versions_dir = os.path.join(migrations_dir, 'versions')
    
    # Check if migrations directory exists
    if not os.path.exists(migrations_dir):
        print("Creating migrations directory")
        os.makedirs(migrations_dir)
        os.makedirs(versions_dir)
    else:
        # Backup versions directory
        backup_time = datetime.now().strftime('%Y%m%d%H%M%S')
        backup_dir = os.path.join('backups', f'migrations_backup_{backup_time}')
        os.makedirs(os.path.dirname(backup_dir), exist_ok=True)
        
        if os.path.exists(versions_dir):
            print(f"Backing up existing versions to {backup_dir}...")
            shutil.copytree(versions_dir, os.path.join(backup_dir, 'versions'))
        
        # Clean versions directory
        if os.path.exists(versions_dir):
            print("Cleaning versions directory...")
            shutil.rmtree(versions_dir)
            os.makedirs(versions_dir)
        else:
            os.makedirs(versions_dir)
    
    return True

def reset_alembic_version_in_db():
    """Reset the alembic_version table in the database."""
    try:
        db_path = os.path.join('instance', 'dev.db')
        if os.path.exists(db_path):
            print(f"Resetting alembic_version in database {db_path}...")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if alembic_version table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            if cursor.fetchone():
                # Delete all records from alembic_version
                cursor.execute("DELETE FROM alembic_version")
                print("Cleared alembic_version table")
            else:
                print("No alembic_version table found, no cleanup needed")
            
            conn.commit()
            conn.close()
        else:
            print(f"Database file not found at {db_path}, no cleanup needed")
    except Exception as e:
        print(f"Error resetting alembic version: {str(e)}")
        return False
    
    return True

def create_fresh_migration():
    """Create a fresh migration based on current models."""
    try:
        print("Creating a fresh migration...")
        # Initialize migration repository if it doesn't exist
        subprocess.run(["flask", "db", "init"], check=True)
        
        # Create a migration
        subprocess.run(["flask", "db", "migrate", "-m", "fresh_start"], check=True)
        
        # Apply the migration
        subprocess.run(["flask", "db", "upgrade"], check=True)
        
        print("Successfully created and applied a fresh migration")
        return True
    except Exception as e:
        print(f"Error creating fresh migration: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting migration fix process...")
    
    # Set Flask environment variables
    os.environ["FLASK_APP"] = "run.py"
    
    if reset_migrations_folder() and reset_alembic_version_in_db():
        if create_fresh_migration():
            print("\nSuccess! The migration history has been reset.")
            print("The application should now start correctly.")
        else:
            print("\nFailed to create fresh migration.")
            sys.exit(1)
    else:
        print("\nFailed to reset migration history.")
        sys.exit(1)
