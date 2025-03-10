#!/bin/bash
set -e

# Create database directory if it doesn't exist
mkdir -p instance

# Install Flask-Migrate if not already installed
pip install Flask-Migrate

echo "Running database migrations..."
# Try to upgrade existing database
if flask db upgrade; then
    echo "Database migrations applied successfully."
else
    # If command fails, initialize the database
    echo "Initializing database..."
    flask db init
    flask db migrate -m "Initial migration"
    flask db upgrade
fi

# Execute the command passed to docker run
exec "$@"
