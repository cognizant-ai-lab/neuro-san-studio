"""Unit tests for health endpoint."""

import logging

from flask import Flask

from apps.legal_discovery import hippo_routes
from apps.legal_discovery.hippo_routes import health_bp


def test_health_endpoint_returns_status_keys():
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert {"neo4j", "chroma", "blocked_requests", "cache"}.issubset(data)


def test_health_reports_neo4j_failure(monkeypatch, caplog):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    class FailingGraphDB:
        @staticmethod
        def driver(*args, **kwargs):  # pragma: no cover - monkeypatched
            raise RuntimeError("boom")

    monkeypatch.setattr(hippo_routes, "GraphDatabase", FailingGraphDB)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/health")

    payload = resp.get_json()
    data = payload["data"]
    meta = payload.get("meta", {})
    assert data["neo4j"] == "fail"
    assert "neo4j_error" in meta and "boom" in meta["neo4j_error"]
    assert "Neo4j health check failed" in caplog.text


def test_health_reports_chroma_failure(monkeypatch, caplog):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    def failing_get(*args, **kwargs):  # pragma: no cover - monkeypatched
        raise RuntimeError("boom")

    monkeypatch.setattr(hippo_routes.requests, "get", failing_get)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/health")

    payload = resp.get_json()
    data = payload["data"]
    meta = payload.get("meta", {})
    assert data["chroma"] == "fail"
    assert "chroma_error" in meta and "boom" in meta["chroma_error"]
    assert "Chroma health check failed" in caplog.text
