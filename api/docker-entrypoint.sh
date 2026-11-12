#!/bin/sh
set -e
# Apply database migrations before starting the service.
alembic upgrade head
exec "$@"
