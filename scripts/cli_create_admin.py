#!/usr/bin/env python3
"""
Standalone script to create admin user
Can be run with: python scripts/cli_create_admin.py
"""
import os
import sys
import uuid
from datetime import datetime

# Add parent directory to path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app import create_app
from app.models.user import User
from app.extensions import db
from werkzeug.security import generate_password_hash

def main():
    app = create_app()
    
    with app.app_context():
        # First, ensure tables exist to prevent "no such table" errors
        try:
            # Create all tables if they don't exist
            db.create_all()
            print("Database tables created/verified")
            
            # Get credentials from environment or use defaults
            username = os.environ.get('ADMIN_USERNAME', 'admin')
            email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
            password = os.environ.get('ADMIN_PASSWORD', 'changeme')
            
            # Check if user exists
            try:
                user = User.query.filter_by(email=email).first()
                if not user:
                    print(f'Creating admin user: {username} ({email})')
                    user = User(
                        id=str(uuid.uuid4()),
                        username=username,
                        email=email,
                        password_hash=generate_password_hash(password),
                        role='admin',
                        is_active=True,
                        is_email_verified=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.session.add(user)
                    db.session.commit()
                    print('Admin user created successfully')
                else:
                    print('Admin user already exists')
            except Exception as e:
                print(f"Error while checking/creating user: {str(e)}")
                db.session.rollback()
                raise
                
        except Exception as e:
            print(f"Database initialization error: {str(e)}")
            raise

if __name__ == '__main__':
    main()
