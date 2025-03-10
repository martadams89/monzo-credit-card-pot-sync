#!/bin/bash
set -e

# Create required directories
mkdir -p instance
mkdir -p app/static/css/dist
mkdir -p app/static/images
mkdir -p app/static/js

echo "Running database migrations..."
# Apply database migrations
flask db upgrade

# Execute the command provided as arguments (e.g., gunicorn command)
exec "$@"
