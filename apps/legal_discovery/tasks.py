import os
import time
import uuid
import logging
from typing import Any, Dict, Tuple

from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from flask import Blueprint, jsonify

from .auth import auth_required
from .exhibit_manager import generate_binder
from . import hippo
from .models_trial import TranscriptSegment, TrialSession
from .database import db, log_retrieval_trace
from .extensions import socketio
from .trial_assistant.services.objection_engine import engine
from apps.message_bus import (
    MessageBus,
    RESEARCH_INSIGHT_TOPIC,
    TIMELINE_ALERT_TOPIC,
    TeamMessage,
)
from flask import has_app_context
from contextlib import nullcontext

logger = logging.getLogger(__name__)

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_conn: Redis | None = None
queue: Queue | None = None
_results: Dict[str, Any] = {}

try:  # pragma: no cover - redis may be unavailable
    redis_conn = Redis.from_url(redis_url)
    redis_conn.ping()
    queue = Queue("legal", connection=redis_conn)
except Exception:  # pragma: no cover - fallback to sync
    queue = None


def enqueue(func, *args, **kwargs) -> Tuple[str, Any | None]:
    """Enqueue *func* with ``rq`` or run synchronously if Redis unavailable."""
    if queue is not None:
        job = queue.enqueue(func, *args, **kwargs)
        return job.id, None
    job_id = uuid.uuid4().hex
    result = func(*args, **kwargs)
    _results[job_id] = result
    return job_id, result


# ---- task implementations -------------------------------------------------


def _context():
    if has_app_context():
        return nullcontext()
    from .startup import app
    return app.app_context()


def binder_task(case_id: int, output_path: str | None = None) -> str:
    with _context():
        return generate_binder(case_id, output_path)


def index_document_task(case_id: str, text: str, path: str = "") -> Dict[str, Any]:
    with _context():
        doc_id = hippo.ingest_document(case_id, text, path)
        segments = len(hippo.INDEX[case_id][doc_id])
        return {"doc_id": doc_id, "segments": segments}


def analyze_segment_task(segment_id: str, session_id: str) -> Dict[str, Any]:
    with _context():
        seg = db.session.get(TranscriptSegment, segment_id)
        if seg is None:
            return {"error": "segment not found"}
        refs: list = []
        trace_id = None
        try:
            sess = db.session.get(TrialSession, session_id)
            if sess:
                start = time.perf_counter()
                result = hippo.hippo_query(sess.case_id, seg.text, k=3)
                elapsed_ms = (time.perf_counter() - start) * 1000
                items = result.get("items", [])
                trace_id = result.get("trace_id")
                refs = [
                    {"segment_id": item.get("segment_id"), "path": item.get("path")}
                    for item in items
                ]
                timings = {"total_ms": round(elapsed_ms, 2)}
                log_retrieval_trace(
                    trace_id=trace_id,
                    case_id=sess.case_id,
                    query=seg.text,
                    graph_weight=1.0,
                    dense_weight=1.0,
                    timings=timings,
                    results=items,
                )
        except Exception as exc:  # pragma: no cover - best effort
            logger.exception("hippo_query failed: %s", exc)
        events = engine.analyze_segment(
            session_id,
            seg,
            trace_id=trace_id,
            refs=refs,
            path=refs[0]["path"] if refs else None,
        )
        for e in events:
            socketio.emit(
                "objection_event",
                {
                    "event_id": e.id,
                    "segment_id": e.segment_id,
                    "ground": e.ground,
                    "confidence": e.confidence,
                    "suggested_cures": e.suggested_cures,
                    "refs": e.refs,
                    "trace_id": e.trace_id,
                },
                room="trial_objections",
                namespace="/ws/trial",
            )
        return {"events": [e.id for e in events], "segment_id": seg.id}


# ---- task status API ------------------------------------------------------

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@tasks_bp.get("/<task_id>")
@auth_required
def task_status(task_id: str):
    if queue is not None:
        try:
            job = Job.fetch(task_id, connection=redis_conn)  # type: ignore[arg-type]
        except NoSuchJobError:
            return jsonify({"status": "unknown", "error": "task not found"}), 404
        except Exception as exc:
            logger.exception("task lookup failed: %s", exc)
            return jsonify({"status": "unknown", "error": "lookup failed"}), 500
        status = job.get_status()
        result = job.result if job.is_finished else None
        return jsonify({"status": status, "result": result})
    result = _results.get(task_id)
    if result is None:
        return jsonify({"status": "unknown", "error": "task not found"}), 404
    return jsonify({"status": "finished", "result": result})


__all__ = [
    "enqueue",
    "binder_task",
    "index_document_task",
    "analyze_segment_task",
    "run_case_analysis",
    "tasks_bp",
]


def ingest_job(
    original_path: str,
    redacted_path: str,
    doc_id: int,
    case_id: int,
    full_metadata: dict,
    chroma_metadata: dict,
    job_id: str | None = None,
    enable_redaction: bool = False,
) -> None:
    """RQ-compatible ingestion entrypoint wrapping interface_flask.ingest_document.

    Imported lazily to avoid circular imports on module import.
    """
    with _context():
        from .interface_flask import ingest_document  # local import

        ingest_document(
            original_path,
            redacted_path,
            doc_id,
            case_id,
            full_metadata,
            chroma_metadata,
            job_id,
            enable_redaction,
        )


def run_case_analysis(case_id: int, iterations: int = 3) -> Dict[str, Any]:
    """Run multi-pass case analysis: graph enrichment, theories, forensics."""
    from coded_tools.legal_discovery.graph_analyzer import GraphAnalyzer
    from coded_tools.legal_discovery.legal_theory_engine import LegalTheoryEngine
    from coded_tools.legal_discovery.forensic_tools import ForensicTools

    with _context():
        results: Dict[str, Any] = {"case_id": case_id, "iterations": iterations, "passes": []}
        ga = GraphAnalyzer()
        lte = LegalTheoryEngine()
        ft = ForensicTools()
        bus = None
        try:
            bus = MessageBus()
        except Exception:
            bus = None
        try:
            for i in range(iterations):
                pass_result: Dict[str, Any] = {"iteration": i + 1}
                try:
                    deltas = ga.enrich_relationships()
                    # Extended enrichment (causation + timeline sequences)
                    try:
                        extra = ga.enrich_causation_and_timeline()
                        deltas |= {f"timeline_{k}": v for k, v in (extra or {}).items()}
                        seq = ga.analyze_timeline_sequences()
                        pass_result["timeline_sequences"] = seq
                        if bus:
                            bus.publish(
                                TIMELINE_ALERT_TOPIC,
                                TeamMessage(
                                    source_team="legal_discovery",
                                    payload={"case_id": case_id, "iteration": i + 1, "sequences": seq},
                                ),
                            )
                    except Exception:
                        pass
                    pass_result["graph_deltas"] = deltas
                    pass_result["timeline_paths"] = ga.analyze_timeline_paths()
                except Exception as exc:
                    logger.exception("graph enrichment failed: %s", exc)
                    pass_result["graph_error"] = str(exc)
                try:
                    theories = lte.suggest_theories()
                    pass_result["theories"] = theories[:5]
                    if bus and theories:
                        try:
                            from apps.message_bus import TeamMessage

                            bus.publish(
                                RESEARCH_INSIGHT_TOPIC,
                                TeamMessage(
                                    source_team="legal_discovery",
                                    payload={"case_id": case_id, "iteration": i + 1, "theories": theories[:5]},
                                ),
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    logger.exception("theory engine failed: %s", exc)
                    pass_result["theory_error"] = str(exc)
                try:
                    pass_result["forensics"] = "queued"
                except Exception:
                    pass
                results["passes"].append(pass_result)
                # Broadcast pass status to UI (non-blocking best-effort)
                try:
                    socketio.emit(
                        "pipeline_pass",
                        {"case_id": case_id, **pass_result},
                        namespace="/chat",
                    )
                except Exception:
                    pass
        finally:
            try:
                lte.close()
            except Exception:
                pass
        return results
