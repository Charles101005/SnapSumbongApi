#!/bin/sh
# Container entrypoint: wait for Postgres -> migrate/seed -> collectstatic -> gunicorn.
set -e

# sync_db = migrate + idempotent seeding (permissions, initial roles, hazard categories)
# so a fresh database boots into a usable state.
echo "[entrypoint] Applying migrations and syncing reference data..."
python manage.py sync_db

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] Starting Gunicorn on 0.0.0.0:8000..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
