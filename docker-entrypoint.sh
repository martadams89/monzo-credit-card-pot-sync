#!/bin/bash
set -e

# Create database directory if it doesn't exist
mkdir -p instance

# Install Flask-Migrate if not already installed
pip install Flask-Migrate

echo "Running database migrations..."
# Apply database migrations
flask db upgrade

# Execute the command provided as arguments (e.g., gunicorn command)
exec "$@"
