"""
Script to create an admin user.
Can be run manually with: flask shell < scripts/create_admin.py
"""
import os
import uuid
from datetime import datetime
from app.models.user import User, Role
from app.extensions import db
from werkzeug.security import generate_password_hash

# Get credentials from environment or use defaults
username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
password = os.environ.get('ADMIN_PASSWORD', 'changeme')

# Check if user exists
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
