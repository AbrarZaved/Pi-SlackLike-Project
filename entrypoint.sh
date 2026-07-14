#!/bin/sh
set -e

# Wait for PostgreSQL to accept connections before starting
if [ -n "$DB_HOST" ]; then
  echo "Waiting for PostgreSQL at $DB_HOST:${DB_PORT:-5432}..."
  while ! nc -z "$DB_HOST" "${DB_PORT:-5432}"; do
    sleep 0.5
  done
  echo "PostgreSQL is up."
fi

# Run whatever command was passed (daphne, celery worker, celery beat, ...)
exec "$@"