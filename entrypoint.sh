#!/bin/sh
# Container entrypoint: wait for Postgres -> migrate/seed -> collectstatic -> gunicorn.
set -e

echo "[entrypoint] Waiting for the database..."
python - <<'PY'
import os
import sys
import time

import psycopg

kwargs = dict(
    host=os.environ.get("DB_HOST", "db"),
    port=int(os.environ.get("DB_PORT", 5432)),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    connect_timeout=3,
)

for attempt in range(1, 61):
    try:
        with psycopg.connect(**kwargs):
            pass
        print("[entrypoint] Database is reachable.")
        break
    except Exception as exc:  # noqa: BLE001 - retry on any connection failure
        print(f"[entrypoint] Database not ready ({attempt}/60): {exc}")
        time.sleep(2)
else:
    print("[entrypoint] FATAL: database never became reachable.", file=sys.stderr)
    sys.exit(1)
PY

# sync_db = migrate + idempotent seeding (permissions, initial roles,
# hazard categories) so a fresh database boots into a usable state.
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
