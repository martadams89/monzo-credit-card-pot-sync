#!/bin/bash
set -e

# Create required directories
mkdir -p instance
mkdir -p app/static/images
mkdir -p app/static/js

# Check if Flask-Migrate is installed
if ! python -c "import flask_migrate" &> /dev/null; then
    echo "Flask-Migrate is not installed. Installing..."
    pip install Flask-Migrate
fi

# Initialize migrations if they don't exist
if [ ! -d "/app/migrations" ]; then
    echo "Migrations folder not found, initializing migrations..."
    flask db init
fi

# Create database tables
echo "Creating database tables..."
python -c "from app import create_app; from app.extensions import db; app = create_app(); app.app_context().push(); db.create_all()"

echo "Running database migrations..."
# Apply database migrations
flask db upgrade

# Create admin user if environment variable is set
if [ "$ADMIN_CREATE_IF_NOT_EXISTS" = "true" ]; then
    echo "Creating admin user if needed..."
    # Run the standalone script instead of using flask shell
    python /app/scripts/cli_create_admin.py
fi

# Execute the command provided as arguments (e.g., gunicorn command)
exec "$@"
