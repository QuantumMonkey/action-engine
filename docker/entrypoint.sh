#!/bin/sh
# Migrate, then serve. Migrations run here rather than at import time so that starting the process
# is the only thing that can change the schema, and so a failed migration stops the container
# instead of leaving it serving against a half-built database.
set -e

python -m action_engine_api.migrations

exec uvicorn action_engine_api:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --no-server-header
