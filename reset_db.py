#!/usr/bin/env python
"""Reset database and migrations completely.

This script:
1. Deletes the existing database file
2. Clears all migration history
3. Creates a fresh database with all tables
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

def reset_database():
    """Reset the entire database."""
    print("Resetting database...")
    
    # Path to database file
    db_path = Path('instance/dev.db')
    
    # Delete database file if it exists
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        os.remove(db_path)
        
    # Ensure instance directory exists
    db_path.parent.mkdir(exist_ok=True)
    
    print("Database reset complete")
    return True

def reset_migrations():
    """Reset the migrations folder."""
    print("Resetting migrations...")
    
    # Path to migrations folder
    migrations_dir = Path('migrations')
    
    # Delete migrations folder if it exists
    if migrations_dir.exists() and migrations_dir.is_dir():
        print(f"Removing existing migrations: {migrations_dir}")
        shutil.rmtree(migrations_dir)
    
    print("Migrations reset complete")
    return True

def create_fresh_database():
    """Create a fresh database with tables using SQLAlchemy."""
    try:
        print("Creating fresh database...")
        
        # Create database with SQLAlchemy
        import sys
        sys.path.append('.')
        
        from app import create_app
        from app.extensions import db
        
        app = create_app()
        with app.app_context():
            # Create all tables
            db.create_all()
            print("All tables created successfully")
            
            # Optional: Initialize with basic settings
            from app.models.setting import Setting
            
            # Add core settings
            settings = [
                Setting(key="app_name", value="Monzo Credit Card Pot Sync"),
                Setting(key="app_version", value="1.0.0"),
                Setting(key="sync_interval", value="60"),  # minutes
                Setting(key="cooldown_period", value="180")  # minutes
            ]
            
            db.session.add_all(settings)
            db.session.commit()
            print("Initial settings created")
        
        return True
    except Exception as e:
        print(f"Error creating fresh database: {e}")
        return False

if __name__ == "__main__":
    print("Starting complete database reset...")
    
    if reset_database() and reset_migrations() and create_fresh_database():
        print("\nSuccess! The database has been completely reset.")
        print("You can start the application with a fresh database.")
    else:
        print("\nError resetting database.")
        sys.exit(1)
