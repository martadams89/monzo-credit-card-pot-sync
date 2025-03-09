#!/bin/bash

echo "Resetting database..."
docker exec -it monzo-credit-card-pot-sync-dev python /app/reset_db.py

echo "Done!"
