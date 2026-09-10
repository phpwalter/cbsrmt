from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "")
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

app = FastAPI(
    title="CBS Radio Mystery Theater Catalog API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


@app.exception_handler(HTTPException)
def http_exception_handler(_, exc: HTTPException):
    return problem(exc.status_code, "Request failed", str(exc.detail))


def fetch_identifiers(cur, entity_type: str, entity_id: UUID | str) -> list[dict[str, str]]:
    view = "api.episode_identifiers" if entity_type == "episode" else "api.broadcast_identifiers"
    id_column = "episode_id" if entity_type == "episode" else "broadcast_id"
    cur.execute(
        f"""
        SELECT namespace, identifier_value
        FROM {view}
        WHERE {id_column} = %s
        ORDER BY namespace, identifier_value
        """,
        (entity_id,),
    )
    return [
        {"namespace": row["namespace"], "value": row["identifier_value"]}
        for row in cur.fetchall()
    ]


def serialize_episode(cur, row: dict[str, Any]) -> dict[str, Any]:
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
        "identifiers": fetch_identifiers(cur, "episode", row["episode_id"]),
    }


def serialize_broadcast(cur, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "broadcastId": row["broadcast_id"],
        "episodeId": row["episode_id"],
        "broadcastAt": row["broadcast_at"],
        "broadcastDate": row["broadcast_date"],
        "broadcastType": row["broadcast_type"],
        "verificationStatus": row["verification_status"],
        "identifiers": fetch_identifiers(cur, "broadcast", row["broadcast_id"]),
    }


def page(data: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "limit": limit,
            "offset": offset,
            "count": total,
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"status": "ok"}


@app.get("/episodes")
def list_episodes(
    year: int | None = Query(default=None, ge=1974, le=1998),
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
            f"""
            SELECT *
            FROM api.episodes e
            {where}
            ORDER BY e.canonical_number NULLS LAST, e.original_air_date, e.episode_id
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        rows = cur.fetchall()
        data = [serialize_episode(cur, row) for row in rows]

    return page(data, total, limit, offset)


@app.get("/episodes/{episode_id}", responses=PROBLEM_404)
def get_episode(episode_id: UUID) -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM api.episodes WHERE episode_id = %s", (episode_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Episode not found")
        return serialize_episode(cur, row)


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
        cur.execute(
            "SELECT count(*) AS count FROM api.broadcasts WHERE episode_id = %s",
            (episode_id,),
        )
        total = cur.fetchone()["count"]
        cur.execute(
            """
            SELECT * FROM api.broadcasts
            WHERE episode_id = %s
            ORDER BY broadcast_date, broadcast_at NULLS LAST, broadcast_id
            LIMIT %s OFFSET %s
            """,
            (episode_id, limit, offset),
        )
        rows = cur.fetchall()
        data = [serialize_broadcast(cur, row) for row in rows]
    return page(data, total, limit, offset)


@app.get("/broadcasts")
def list_broadcasts(
    year: int | None = Query(default=None, ge=1974, le=1998),
    broadcast_type: str | None = Query(
        default=None, alias="type", pattern="^(original|rerun|unknown)$"
    ),
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
        cur.execute(
            f"SELECT count(DISTINCT b.broadcast_id) AS count FROM api.broadcasts b {join} {where}",
            params,
        )
        total = cur.fetchone()["count"]
        cur.execute(
            f"""
            SELECT DISTINCT b.*
            FROM api.broadcasts b
            {join}
            {where}
            ORDER BY b.broadcast_date, b.broadcast_at NULLS LAST, b.broadcast_id
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        rows = cur.fetchall()
        data = [serialize_broadcast(cur, row) for row in rows]

    return page(data, total, limit, offset)


@app.get("/broadcasts/{broadcast_id}", responses=PROBLEM_404)
def get_broadcast(broadcast_id: UUID) -> dict[str, Any]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM api.broadcasts WHERE broadcast_id = %s", (broadcast_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        return serialize_broadcast(cur, row)
