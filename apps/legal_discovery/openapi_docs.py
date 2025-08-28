from __future__ import annotations

import os
from flask import Blueprint, jsonify, Response


docs_bp = Blueprint("docs", __name__)


@docs_bp.get("/openapi.json")
def openapi_spec() -> Response:
    """Return a minimal OpenAPI 3.0 spec covering key endpoints.

    This seed spec is hand-authored to avoid new dependencies. We can later
    replace it with apispec/flask-smorest for automatic generation.
    """

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Neuro-San Studio 2 API",
            "version": os.environ.get("API_VERSION", "0.1"),
            "description": "Core endpoints for Legal Discovery (health, readiness, vector, upload).",
        },
        "paths": {
            "/api/health": {
                "get": {
                    "summary": "Service health",
                    "responses": {
                        "200": {
                            "description": "Health status",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "ok": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "neo4j": {"type": "string"},
                                                    "chroma": {"type": "string"},
                                                    "postgres": {"type": "string"},
                                                    "redis": {"type": "string"},
                                                },
                                            },
                                            "meta": {"type": "object"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/readiness": {
                "get": {"summary": "Service readiness", "responses": {"200": {"description": "Ready"}, "503": {"description": "Not ready"}}}
            },
            "/api/upload/status": {
                "get": {
                    "summary": "Get upload/ingestion status by job_id",
                    "parameters": [
                        {"name": "job_id", "in": "query", "schema": {"type": "string"}, "required": True, "description": "Repeatable; may be comma-separated"}
                    ],
                    "responses": {"200": {"description": "Map of job_id -> status"}}
                }
            },
            "/api/vector/search": {
                "get": {
                    "summary": "Search vectors",
                    "parameters": [
                        {"name": "q", "in": "query", "schema": {"type": "string"}},
                        {"name": "n", "in": "query", "schema": {"type": "integer", "default": 10}},
                    ],
                    "responses": {"200": {"description": "Results"}},
                }
            },
            "/api/vector/count": {
                "get": {"summary": "Vector count", "responses": {"200": {"description": "Count"}}}
            },
            "/api/upload": {
                "post": {
                    "summary": "Upload documents",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
                                        "source": {"type": "string", "enum": ["user", "opp_counsel", "court"]},
                                        "redaction": {"type": "boolean", "description": "Enable privilege redaction (default false)"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {"202": {"description": "Accepted", "content": {"application/json": {"schema": {"type": "object"}}}}},
                }
            },
        },
    }
    return jsonify(spec)


@docs_bp.get("/docs")
def swagger_ui() -> Response:
    """Serve Swagger UI from CDN bound to /openapi.json.

    Avoids extra Python dependencies. Suitable for dev/staging docs.
    """
    html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Neuro-San Studio 2 — API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
    </script>
  </body>
  </html>
    """
    return Response(html, mimetype="text/html")
