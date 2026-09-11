from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.db import close_pool, db_connection, open_pool

REQUIRED_DB_ROLE = os.getenv("CBSRMT_REQUIRED_DB_ROLE", "cbsrmt_api")
SERVICE_NAME = "cbsrmt-api"
logger = logging.getLogger(SERVICE_NAME)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(message)s")

PROBLEM_404 = {
    404: {
        "description": "Resource not found",
        "content": {
            "application/problem+json": {
                "schema": {
                    "type": "object",
                    "required": ["type", "title", "status"],
                    "properties": {
                        "type": {"type": "string"},
                        "title": {"type": "string"},
                        "status": {"type": "integer"},
                        "detail": {"type": "string"},
                    },
                }
            }
        },
    }
}
PROBLEM_503 = {
    503: {
        "description": "Service is not ready",
        "content": {
            "application/problem+json": {
                "schema": {
                    "type": "object",
                    "required": ["type", "title", "status"],
                    "properties": {
                        "type": {"type": "string"},
                        "title": {"type": "string"},
                        "status": {"type": "integer"},
                        "detail": {"type": "string"},
                    },
                }
            }
        },
    }
}


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "service": SERVICE_NAME, **fields}
    logger.info(json.dumps(payload, default=str, separators=(",", ":")))


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
    )


def database_diagnostics() -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM api.runtime_access_check()")
        row = cur.fetchone()
    return dict(row)


def assert_runtime_role() -> None:
    diagnostics = database_diagnostics()
    if not diagnostics["is_api_member"]:
        raise RuntimeError(
            f"Database login {diagnostics['login_role']!r} is not a member of {REQUIRED_DB_ROLE!r}"
        )
    if not diagnostics["can_read_api"]:
        raise RuntimeError("Database login cannot read api.* projections")
    if diagnostics["can_read_catalog_directly"]:
        raise RuntimeError("Database login can read catalog tables directly")
    if diagnostics["can_read_provenance_directly"]:
        raise RuntimeError("Database login can read provenance tables directly")


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    assert_runtime_role()
    log_event("service_started")
    try:
        yield
    finally:
        close_pool()
        log_event("service_stopped")


app = FastAPI(
    title="CBS Radio Mystery Theater Catalog API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=elapsed_ms,
        )


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException):
    return problem(exc.status_code, "Request failed", str(exc.detail))


def serialize_episode(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "episodeId": row["episode_id"],
        "canonicalNumber": row["canonical_number"],
        "title": row["title"],
        "subtitle": row["subtitle"],
        "synopsis": row["synopsis"],
        "originalAirDate": row["original_air_date"],
        "durationSeconds": row["duration_seconds"],
        "seriesName": row["series_name"],
        "verificationStatus": row["verification_status"],
        "identifiers": row["identifiers"],
    }


def serialize_broadcast(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "broadcastId": row["broadcast_id"],
        "episodeId": row["episode_id"],
        "broadcastAt": row["broadcast_at"],
        "broadcastDate": row["broadcast_date"],
        "broadcastType": row["broadcast_type"],
        "verificationStatus": row["verification_status"],
        "identifiers": row["identifiers"],
    }


def page(data: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"data": data, "meta": {"limit": limit, "offset": offset, "count": total}}


@app.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", responses=PROBLEM_503)
def readiness() -> dict[str, str]:
    try:
        assert_runtime_role()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Service not ready: {exc}") from exc
    return {"status": "ok"}


@app.get("/health", responses=PROBLEM_503)
def health() -> dict[str, str]:
    return readiness()


@app.get("/episodes")
def list_episodes(
    year: int | None = Query(default=None, ge=1974),
    title: str | None = None,
    show_number: int | None = Query(default=None, alias="showNumber", ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if year is not None:
        clauses.append("EXTRACT(YEAR FROM e.original_air_date) = %s")
        params.append(year)
    if title:
        clauses.append("e.title ILIKE %s")
        params.append(f"%{title}%")
    if show_number is not None:
        clauses.append("e.canonical_number = %s")
        params.append(show_number)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS count FROM api.episodes e {where}", params)
        total = cur.fetchone()["count"]
        cur.execute(
            f"SELECT * FROM api.episodes e {where} ORDER BY e.canonical_number NULLS LAST, e.original_air_date, e.episode_id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        data = [serialize_episode(row) for row in cur.fetchall()]
    return page(data, total, limit, offset)


@app.get("/episodes/{episode_id}", responses=PROBLEM_404)
def get_episode(episode_id: UUID) -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM api.episodes WHERE episode_id = %s", (episode_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Episode not found")
        return serialize_episode(row)


@app.get("/episodes/{episode_id}/broadcasts", responses=PROBLEM_404)
def get_episode_broadcasts(
    episode_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM api.episodes WHERE episode_id = %s", (episode_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        cur.execute("SELECT count(*) AS count FROM api.broadcasts WHERE episode_id = %s", (episode_id,))
        total = cur.fetchone()["count"]
        cur.execute(
            "SELECT * FROM api.broadcasts WHERE episode_id = %s ORDER BY broadcast_date, broadcast_at NULLS LAST, broadcast_id LIMIT %s OFFSET %s",
            (episode_id, limit, offset),
        )
        data = [serialize_broadcast(row) for row in cur.fetchall()]
    return page(data, total, limit, offset)


@app.get("/broadcasts")
def list_broadcasts(
    year: int | None = Query(default=None, ge=1974),
    broadcast_type: str | None = Query(default=None, alias="type", pattern="^(original|rerun|unknown)$"),
    otrw_number: int | None = Query(default=None, alias="otrwNumber", ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    join = ""
    if year is not None:
        clauses.append("EXTRACT(YEAR FROM b.broadcast_date) = %s")
        params.append(year)
    if broadcast_type is not None:
        clauses.append("b.broadcast_type = %s")
        params.append(broadcast_type)
    if otrw_number is not None:
        join = "JOIN api.broadcast_identifiers i ON i.broadcast_id = b.broadcast_id"
        clauses.append("i.namespace = 'otrwalter.broadcast_number'")
        clauses.append("i.identifier_value = %s")
        params.append(str(otrw_number))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(DISTINCT b.broadcast_id) AS count FROM api.broadcasts b {join} {where}", params)
        total = cur.fetchone()["count"]
        cur.execute(
            f"SELECT DISTINCT b.* FROM api.broadcasts b {join} {where} ORDER BY b.broadcast_date, b.broadcast_at NULLS LAST, b.broadcast_id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        data = [serialize_broadcast(row) for row in cur.fetchall()]
    return page(data, total, limit, offset)


@app.get("/broadcasts/{broadcast_id}", responses=PROBLEM_404)
def get_broadcast(broadcast_id: UUID) -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM api.broadcasts WHERE broadcast_id = %s", (broadcast_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        return serialize_broadcast(row)
