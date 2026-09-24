# REQ-16. One stage, no build tooling in the final image, and nothing in it that the service does
# not need at runtime.
#
# Two deliberate choices:
#  1. The served database is a FIXTURE baked in at build time. This image is a demo of a read-only
#     surface, so it ships with data that is safe to show; a real deployment mounts its own file
#     over /data/sample.db and the server is read-only either way.
#  2. No signing key is baked in. Without ACTION_ENGINE_JWT_SECRET the auth layer refuses every
#     protected route with a typed 503 rather than serving them open. An image that is useless until
#     configured is the correct default for one that fronts a database.

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACTION_ENGINE_DB=/data/sample.db \
    ACTION_ENGINE_AUDIT_LOG=/data/audit.jsonl \
    ACTION_ENGINE_DATABASE_URL=sqlite:////data/state.db \
    PORT=8000

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY sqlite_mcp_server ./sqlite_mcp_server
COPY action_engine_api ./action_engine_api
COPY scripts ./scripts
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN pip install --no-cache-dir ".[api,postgres]" \
    && mkdir -p /data \
    && python scripts/make_fixture.py /data/sample.db \
    && chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /data

USER app
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
