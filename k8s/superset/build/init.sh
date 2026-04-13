#!/bin/bash
set -e

echo "Starting Superset Initialization..."

# Setup admin user
superset fab create-admin \
  --username admin \
  --firstname Superset \
  --lastname Admin \
  --email admin@superset.com \
  --password admin || true

# Migrate database
superset db upgrade

# Initialize roles/permissions
superset init

echo "Superset initialized successfully!"

# Start the web server
echo "Starting web server..."
# Using the standard command from the modern superset docker image
exec gunicorn \
    -w 2 \
    -k gthread \
    --threads 4 \
    --timeout 120 \
    -b 0.0.0.0:8088 \
    --limit-request-line 0 \
    --limit-request-field_size 0 \
    "superset.app:create_app()"
