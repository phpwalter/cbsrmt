from __future__ import annotations

import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app

DATABASE_URL = os.getenv("DATABASE_URL")
API_DATABASE_URL = os.getenv("API_DATABASE_URL") or DATABASE_URL
pytestmark = pytest.mark.skipif(not API_DATABASE_URL, reason="API_DATABASE_URL not configured")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_liveness(client: TestClient) -> None:
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/live")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")


def test_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/live", headers={"X-Request-ID": "integration-test-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "integration-test-123"


def test_list_episodes(client: TestClient) -> None:
    response = client.get("/episodes", params={"year": 1982, "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 127
    assert payload["meta"]["limit"] == 10
    assert payload["meta"]["offset"] == 0
    assert len(payload["data"]) == 10
    assert payload["data"][0]["canonicalNumber"] == 1273
    assert payload["data"][0]["identifiers"] == [
        {"namespace": "cbsrmt.show_number", "value": "1273"}
    ]


def test_lookup_episode_by_show_number(client: TestClient) -> None:
    response = client.get("/episodes", params={"showNumber": 1273})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 1
    assert payload["data"][0]["title"] == "The Acquisition"


def test_lookup_broadcast_by_otrw_number(client: TestClient) -> None:
    response = client.get("/broadcasts", params={"otrwNumber": 2711})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 1
    assert payload["data"][0]["broadcastDate"] == "1982-01-04"
    assert payload["data"][0]["broadcastType"] == "original"
    assert payload["data"][0]["identifiers"] == [
        {"namespace": "otrwalter.broadcast_number", "value": "2711"}
    ]


def test_episode_detail_and_broadcasts(client: TestClient) -> None:
    listing = client.get("/episodes", params={"showNumber": 1273}).json()
    episode_id = listing["data"][0]["episodeId"]

    detail = client.get(f"/episodes/{episode_id}")
    assert detail.status_code == 200
    assert detail.json()["canonicalNumber"] == 1273

    broadcasts = client.get(f"/episodes/{episode_id}/broadcasts")
    assert broadcasts.status_code == 200
    payload = broadcasts.json()
    assert payload["meta"]["count"] == 1
    assert payload["data"][0]["broadcastDate"] == "1982-01-04"


def test_broadcast_type_alias(client: TestClient) -> None:
    response = client.get("/broadcasts", params={"type": "original", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 127
    assert all(item["broadcastType"] == "original" for item in payload["data"])


def test_not_found_problem_json(client: TestClient) -> None:
    response = client.get("/episodes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["status"] == 404
    assert payload["detail"] == "Episode not found"


def test_api_reads_projection_views() -> None:
    with psycopg.connect(API_DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM api.episodes")
        assert cur.fetchone()[0] == 127
        cur.execute("SELECT count(*) FROM api.broadcasts")
        assert cur.fetchone()[0] == 127
