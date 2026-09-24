"""The HTTP surface (REQ-10, REQ-11). Chapter B, docs/planning/chapter-B-http-api.md.

What is built here: the generated OpenAPI document, bearer auth on every route except the two open
ones, and the three read tools behind it. What is NOT built yet, and is still red in
tests/acceptance/test_http_api.py: rate limiting (REQ-12), audit rows (REQ-13), the idempotent
export (REQ-14) and Postgres migrations (REQ-15). Those routes are deliberately absent rather than
stubbed: a documented route that lies is worse than a missing one.

The read path delegates to the existing guards, so the read-only guarantee is the same one chapter 1
already proves. This module adds no way to write.
"""

import os

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sqlite_mcp_server.guards import PathLock, RefusalError, open_readonly, run_query

from .audit import AuditContext, AuditLog, new_request_id
from .auth import AuthRefusal, Identities, authenticate

DB_ENV = "ACTION_ENGINE_DB"
OPEN_ROUTES = ("/healthz", "/openapi.json")
# Reading one's own trail is not an action the trail exists to record, and self-referential rows make
# any count untestable. Decision 2 in the chapter B spec.
UNAUDITED_PREFIX = "/v1/audit"

app = FastAPI(
    title="action-engine",
    version="0.2.0-dev",
    description="Read-only HTTP surface over one local SQLite database. It cannot write.",
    docs_url=None,       # the generated document is the contract; the browser UI is not
    redoc_url=None,
    openapi_url=None,    # served explicitly below so the document lists itself (REQ-10)
)

_lock: PathLock = None


def lock() -> PathLock:
    """Resolve the path lock lazily so importing the app never touches the filesystem."""
    global _lock
    if _lock is None:
        path = os.environ.get(DB_ENV)
        if not path:
            raise RefusalError("not_configured", detail="%s is not set" % DB_ENV)
        _lock = PathLock(path)
    return _lock


def refusal(status: int, reason: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"refused": True, "reason": reason, "detail": detail})


_audit = AuditLog()


def audit_log() -> AuditLog:
    """Re-read the configured path on each call so tests and deployments can point it somewhere
    without importing the app twice."""
    global _audit
    if _audit.path != (os.environ.get("ACTION_ENGINE_AUDIT_LOG") or _audit.path):
        _audit = AuditLog()
    return _audit


@app.middleware("http")
async def require_bearer_and_audit(request: Request, call_next):
    """REQ-11 and REQ-13. Auth runs before any handler, so no route can forget it; the audit row is
    written after, so no handler can forget that either, or write two.

    A rejected request writes no row: its identities are exactly what could not be established
    (decision 1 in the chapter B spec). Every response carries X-Request-Id, including refusals, so
    a caller can quote one id when asking what happened.
    """
    request_id = new_request_id()
    if request.url.path in OPEN_ROUTES:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    try:
        identities = authenticate(request.headers.get("Authorization"))
    except AuthRefusal as exc:
        status = 503 if exc.reason == "auth_not_configured" else 401
        response = refusal(status, exc.reason, exc.detail)
        response.headers["X-Request-Id"] = request_id
        return response

    request.state.identities = identities
    ctx = AuditContext(request_id=request_id, identities=identities,
                       route=request.scope.get("route").path if request.scope.get("route") else request.url.path)
    ctx.idempotency_key = request.headers.get("Idempotency-Key", "")
    request.state.audit = ctx

    try:
        response = await call_next(request)
    except Exception:
        ctx.outcome = "error"
        audit_log().append(ctx.to_row(500))
        raise

    ctx.route = request.scope["route"].path if request.scope.get("route") else request.url.path
    if not (ctx.suppressed or ctx.route.startswith(UNAUDITED_PREFIX)):
        audit_log().append(ctx.to_row(response.status_code))
    response.headers["X-Request-Id"] = request_id
    return response


class QueryRequest(BaseModel):
    sql: str = Field(..., description="A single SELECT statement. Anything else is refused.")


@app.get("/healthz", summary="Liveness, open and unaudited", tags=["meta"])
def healthz() -> dict:
    return {"status": "ok", "version": app.version, "rate_limit_per_minute": None}


@app.get("/openapi.json", summary="The generated OpenAPI document for this service", tags=["meta"])
def openapi_document() -> JSONResponse:
    return JSONResponse(get_openapi(title=app.title, version=app.version,
                                    description=app.description, routes=app.routes))


@app.get("/v1/whoami", summary="The three identities this token resolves to", tags=["identity"])
def whoami(request: Request) -> dict:
    """Deliberately public within the API: a caller should be able to see exactly what the audit row
    will say about them before they act (ADR-0001)."""
    request.state.audit.note("whoami")
    ids: Identities = request.state.identities
    return {"agent_id": ids.agent_id, "subject_id": ids.subject_id,
            "initiator_id": ids.initiator_id, "unattended": ids.is_unattended}


@app.get("/v1/audit/_count", summary="How many audit rows exist for this caller", tags=["audit"])
def audit_count(request: Request) -> JSONResponse:
    ids: Identities = request.state.identities
    return JSONResponse({"count": audit_log().count(ids.subject_id)})


@app.get("/v1/audit/{request_id}", summary="The audit row for one request, for its own subject",
         tags=["audit"])
def audit_row(request_id: str, request: Request) -> JSONResponse:
    ids: Identities = request.state.identities
    row = audit_log().get(request_id, ids.subject_id)
    if row is None:
        return refusal(404, "no_such_request", "no audit row for that id under this subject")
    return JSONResponse(row)


@app.get("/v1/tables", summary="List the user tables in the locked database", tags=["read"])
def list_tables(request: Request) -> JSONResponse:
    ctx = request.state.audit
    ctx.note("list_tables")
    try:
        conn = open_readonly(lock())
    except RefusalError as exc:
        ctx.refuse(exc.payload.get("error", "refused"))
        return refusal(503, exc.payload.get("error", "refused"), exc.payload.get("detail", ""))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name").fetchall()
    finally:
        conn.close()
    ctx.rows_returned = len(rows)
    return JSONResponse({"tables": [r[0] for r in rows]})


@app.get("/v1/tables/{table}/schema", summary="Return one table's CREATE statement and columns",
         tags=["read"])
def table_schema(table: str, request: Request) -> JSONResponse:
    ctx = request.state.audit
    ctx.note("table_schema", {"table": table})
    try:
        conn = open_readonly(lock())
    except RefusalError as exc:
        ctx.refuse(exc.payload.get("error", "refused"))
        return refusal(503, exc.payload.get("error", "refused"), exc.payload.get("detail", ""))
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                           (table,)).fetchone()
        if row is None:
            ctx.refuse("no_such_table")
            return refusal(404, "no_such_table", "no table named %r in the locked database" % table)
        columns = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % _quote(table)).fetchall()]
    finally:
        conn.close()
    return JSONResponse({"table": table, "sql": row[0], "columns": columns})


@app.post("/v1/query", summary="Run one read-only SELECT against the locked database", tags=["read"])
def query(body: QueryRequest, request: Request) -> JSONResponse:
    ctx = request.state.audit
    # The SQL is hashed into args_hash and never stored: a refused query is the likeliest place for
    # an argument to carry something sensitive.
    ctx.note("run_readonly_query", {"sql": body.sql})
    try:
        result = run_query(lock(), body.sql)
    except RefusalError as exc:
        payload = exc.payload
        ctx.refuse(payload.get("error", "refused"))
        return refusal(400, payload.get("error", "refused"), payload.get("detail", ""))
    ctx.rows_returned = result.get("row_count", 0)
    return JSONResponse(result)


def _quote(identifier: str) -> str:
    """PRAGMA takes no parameters, so the table name is quoted rather than bound. The name has
    already been matched against sqlite_master above, and a double quote is doubled here so a
    crafted name cannot break out."""
    return '"%s"' % identifier.replace('"', '""')
