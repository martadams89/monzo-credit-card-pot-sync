#!/bin/bash

set -e

# Function to perform health checks
run_health_checks() {
    echo "Running application health checks..."
    python -m app.healthcheck
    return $?
}

# Create required directories with proper permissions
mkdir -p /app/instance
mkdir -p /app/logs
mkdir -p /app/backups
mkdir -p /app/migrations/versions
mkdir -p /app/app/static/css/dist
mkdir -p /app/app/static/css/src

# Set proper permissions for data directories
chmod 755 /app/instance
chmod 755 /app/logs
chmod 755 /app/backups
chmod 755 /app/migrations/versions
chmod 755 /app/app/static/css/dist
chmod 755 /app/app/static/css/src

# Ensure input.css exists
if [ ! -f /app/app/static/css/src/input.css ]; then
  echo "@tailwind base;
@tailwind components;
@tailwind utilities;" > /app/app/static/css/src/input.css
  echo "Created input.css"
fi

# Skip CSS build since it's done during image build
# Only rebuild in development mode
if [ "${FLASK_ENV}" = "development" ]; then
    echo "Development mode detected, rebuilding CSS..."
    cd /app && npm run build-css
fi

# Ensure database directory is writable
touch /app/instance/test_file && rm /app/instance/test_file || {
    echo "Error: Cannot write to /app/instance directory"
    exit 1
}

# SIMPLIFIED DATABASE SETUP - Skip migrations and just create tables directly
echo "Initializing database..."
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.extensions import db
    db.create_all()
    print('Database tables created successfully')
" || {
    echo "Warning: There was an issue creating database tables"
}

# Create admin user if environment variables are provided
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "Creating admin user from environment variables..."
    python -c "
import sys
sys.path.append('/app')
from app import create_app
from app.models.user import User
from app.extensions import db
from datetime import datetime

try:
    app = create_app()
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(email='$ADMIN_EMAIL').first()
        if not existing_user:
            user = User(username='$ADMIN_USERNAME', email='$ADMIN_EMAIL', is_admin=True)
            user.set_password('$ADMIN_PASSWORD')
            # Set timestamps
            user.created_at = datetime.utcnow()
            user.updated_at = datetime.utcnow()
            db.session.add(user)
            db.session.commit()
            print('Admin user created successfully')
        else:
            print('Admin user already exists')
        
        # Save admin registration code if provided
        if '$ADMIN_REGISTRATION_CODE':
            from app.models.setting import Setting
            setting = Setting.query.filter_by(key='admin_registration_code').first()
            if setting:
                setting.value = '$ADMIN_REGISTRATION_CODE'
            else:
                setting = Setting(key='admin_registration_code', value='$ADMIN_REGISTRATION_CODE')
                db.session.add(setting)
            db.session.commit()
            print('Admin registration code saved')
except Exception as e:
    print(f'Error creating admin user: {e}')
"
fi

# Run health checks
if ! run_health_checks; then
    echo "Health checks failed! Please check the application logs for more details."
    exit 1
fi

# Start the application
echo "Starting application with: $@"
exec "$@"