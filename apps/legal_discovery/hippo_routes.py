"""Flask blueprint exposing minimal HippoRAG endpoints."""
from __future__ import annotations

import logging
import os
import time
import uuid

import requests
from flask import Blueprint, jsonify, request
from .auth import auth_required

try:  # pragma: no cover - optional dependency
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - driver may be absent
    GraphDatabase = None

from . import hippo
from .database import db, log_retrieval_trace, log_objection_resolution
from .extensions import socketio, limiter, user_limit_key, blocked_requests
from .models import ObjectionEvent
from .models_trial import TranscriptSegment, TrialSession
from .trial_assistant import bp as trial_bp
from .trial_assistant.services.objection_engine import engine
from .tasks import enqueue, index_document_task, analyze_segment_task

bp = Blueprint("hippo", __name__, url_prefix="/api/hippo")
objections_bp = Blueprint("objections", __name__, url_prefix="/api/objections")
health_bp = Blueprint("health", __name__, url_prefix="/api")

logger = logging.getLogger(__name__)


@health_bp.get("/health")
def health() -> 'flask.Response':
    """Report connectivity status for Neo4j and Chroma services."""
    neo4j_status = "ok"
    chroma_status = "ok"

    try:  # pragma: no cover - external service
        if GraphDatabase is None:
            raise RuntimeError("neo4j driver missing")
        uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        pwd = os.environ.get("NEO4J_PASSWORD")
        auth = (user, pwd) if pwd else None
        db_name = os.environ.get("NEO4J_DATABASE", "neo4j")
        with GraphDatabase.driver(uri, auth=auth) as driver:
            with driver.session(database=db_name) as session:
                session.run("RETURN 1")
    except Exception:
        neo4j_status = "fail"

    try:  # pragma: no cover - external service
        host = os.environ.get("CHROMA_HOST", "localhost")
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        resp = requests.get(
            f"http://{host}:{port}/api/v1/heartbeat", timeout=2
        )
        if resp.status_code != 200:
            raise RuntimeError("chroma heartbeat failed")
    except Exception:
        chroma_status = "fail"

    return jsonify({
        "neo4j": neo4j_status,
        "chroma": chroma_status,
        "blocked_requests": dict(blocked_requests),
    })


@bp.post("/index")
@auth_required
def index_document():
    data = request.get_json() or {}
    case_id = data.get("case_id")
    text = data.get("text")
    path = data.get("doc_path", "")
    if not case_id or not text:
        return jsonify({"error": "case_id and text required"}), 400
    task_id, result = enqueue(index_document_task, case_id, text, path)
    if result is not None:
        return jsonify({"task_id": task_id, **result})
    return jsonify({"task_id": task_id}), 202


@bp.post("/query")
@limiter.limit("100/minute")
@limiter.limit("50/minute", key_func=user_limit_key)
@auth_required
def query_document():
    data = request.get_json() or {}
    case_id = data.get("case_id")
    query = data.get("query", "")
    k = int(data.get("k", 10))
    graph_weight = float(data.get("graph_weight", 1.0))
    dense_weight = float(data.get("dense_weight", 1.0))
    return_paths = data.get("return_paths", True)
    if not case_id:
        return jsonify({"error": "case_id required"}), 400

    overall_start = time.perf_counter()
    query_start = overall_start
    result = hippo.hippo_query(case_id, query, k=k)
    query_ms = (time.perf_counter() - query_start) * 1000

    items = result.get("items", [])
    format_start = time.perf_counter()
    for item in items:
        scores = item.get("scores", {})
        graph_score = scores.get("graph", 0) * graph_weight
        dense_score = scores.get("dense", 0) * dense_weight
        cross_score = scores.get("cross", 0)
        scores["graph"] = graph_score
        scores["dense"] = dense_score
        scores["hybrid"] = graph_score + dense_score + cross_score
        if not return_paths:
            item.pop("path", None)

    format_ms = (time.perf_counter() - format_start) * 1000
    total_ms = (time.perf_counter() - overall_start) * 1000

    items.sort(key=lambda r: r["scores"]["hybrid"], reverse=True)
    trace_id = uuid.uuid4().hex
    timings = {
        "query_ms": round(query_ms, 2),
        "format_ms": round(format_ms, 2),
        "total_ms": round(total_ms, 2),
    }

    log_retrieval_trace(
        trace_id=trace_id,
        case_id=case_id,
        query=query,
        graph_weight=graph_weight,
        dense_weight=dense_weight,
        timings=timings,
        results=items,
    )
    logger.info("hippo query trace %s %.2fms", trace_id, total_ms)

    return jsonify({"items": items, "trace_id": trace_id, "timings": timings})


@objections_bp.post("/analyze-segment")
@auth_required
def analyze_segment():
    """Run objection analysis on a transcript segment.

    The segment text is stored, analysed by the objection engine and
    supporting reference passages are pulled via ``hippo_query``.  Any
    generated objection events are persisted and broadcast to clients
    listening on the ``trial_objections`` Socket.IO room.
    """

    data = request.get_json() or {}
    session_id = data.get("session_id")
    text = data.get("text", "")
    if not session_id or not text:
        return jsonify({"error": "session_id and text required"}), 400
    seg = TranscriptSegment(
        session_id=session_id,
        text=text,
        t0_ms=data.get("t0_ms"),
        t1_ms=data.get("t1_ms"),
        speaker=data.get("speaker"),
        confidence=data.get("confidence"),
    )
    db.session.add(seg)
    db.session.commit()
    task_id, result = enqueue(analyze_segment_task, seg.id, session_id)
    if result is not None:
        return jsonify({"task_id": task_id, **result})
    return jsonify({"task_id": task_id, "segment_id": seg.id}), 202


@trial_bp.post("/objection/action")
@auth_required
def objection_action():
    """Persist an attorney's chosen cure and notify listeners."""

    data = request.get_json() or {}
    evt_id = data.get("event_id")
    cure = data.get("cure") or data.get("action")
    if not evt_id or not cure:
        return jsonify({"error": "event_id and cure required"}), 400

    log_objection_resolution(event_id=evt_id, chosen_cure=cure)
    socketio.emit(
        "objection_cure_chosen",
        {"event_id": evt_id, "cure": cure},
        room="trial_objections",
        namespace="/ws/trial",
    )
    evt = db.session.get(ObjectionEvent, evt_id)
    if evt:
        socketio.emit(
            "clear_highlights",
            {"segment_id": evt.segment_id},
            room="trial_objections",
            namespace="/ws/trial",
        )
    return jsonify({"ok": True})


@socketio.on("objection_cure_chosen", namespace="/ws/trial")
def objection_cure_chosen(data):
    """Record an attorney's chosen cure and clear active highlights."""

    evt_id = data.get("event_id")
    cure = data.get("cure")
    if not evt_id:
        return
    log_objection_resolution(event_id=evt_id, chosen_cure=cure)
    evt = db.session.get(ObjectionEvent, evt_id)
    if evt:
        socketio.emit(
            "clear_highlights",
            {"segment_id": evt.segment_id},
            room="trial_objections",
            namespace="/ws/trial",
        )
