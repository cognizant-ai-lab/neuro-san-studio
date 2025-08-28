import atexit
import csv
import difflib
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from difflib import SequenceMatcher
from io import BytesIO, StringIO

import fitz
import schedule
import spacy
from flask import Flask, Response, jsonify, render_template, request, send_file, g
import uuid
from more_itertools import chunked
import structlog
from pyhocon import ConfigFactory
from spacy.cli import download as spacy_download
from weasyprint import HTML
from werkzeug.utils import secure_filename
from pydantic import ValidationError

from . import settings
from . import presentation_ws  # noqa: F401
from .chat_state import user_input_queue
from .chain_logger import ChainEventType, log_event
from .database import db
from .exhibit_routes import exhibits_bp
from .cache import redis_cache, invalidate_prefix
from .extensions import (
    blocked_requests,
    configure_logging,
    init_tracing,
    limiter,
    metrics,
    redis_client,
    socketio,
    tracer,
)
from .feature_flags import FEATURE_FLAGS
from .hippo_routes import bp as hippo_bp, objections_bp, health_bp
from .openapi_docs import docs_bp
from .api_utils import ok, err
from .tasks import tasks_bp
from .trial_assistant import bp as trial_assistant_bp
from .trial_prep_routes import trial_prep_bp
from .validators import NarrativeDiscrepancyAnalyzePayload
from apps.legal_discovery.models import (
    Agent,
    CalendarEvent,
    Case,
    CauseOfAction,
    DepositionQuestion,
    DepositionReviewLog,
    Document,
    DocumentMetadata,
    Element,
    Fact,
    LegalReference,
    LegalTheory,
    RedactionAudit,
    RedactionLog,
    TimelineEvent,
    Witness,
    ChainOfCustodyLog,
    DocumentSource,
    MessageAuditLog,
    NarrativeDiscrepancy,
    DocumentVersion,
    VoiceCache,
)
from coded_tools.legal_discovery.bates_numbering import (
    BatesNumberingService,
    stamp_pdf,
)
from coded_tools.legal_discovery.deposition_prep import DepositionPrep
from coded_tools.legal_discovery.legal_crawler import LegalCrawler
from coded_tools.legal_discovery.narrative_discrepancy_detector import (
    NarrativeDiscrepancyDetector,
)

try:
    from apps.legal_discovery.legal_discovery import (
        legal_discovery_thinker,
        set_up_legal_discovery_assistant,
        tear_down_legal_discovery_assistant,
    )
except Exception:  # pragma: no cover - optional dependency
    legal_discovery_thinker = None

    def set_up_legal_discovery_assistant(*args, **kwargs):
        return None, None

    def tear_down_legal_discovery_assistant(*args, **kwargs):
        return None


# Configure logging and tracing before any other setup
configure_logging()
logger = structlog.get_logger(__name__)

bates_service = BatesNumberingService()

# Resolve project root relative to this file so Docker and local runs share paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ["AGENT_MANIFEST_FILE"] = os.environ.get(
    "AGENT_MANIFEST_FILE",
    os.path.join(BASE_DIR, "registries", "manifest.hocon"),
)
os.environ["AGENT_TOOL_PATH"] = os.environ.get(
    "AGENT_TOOL_PATH",
    os.path.join(BASE_DIR, "coded_tools"),
)
os.environ["AGENT_LLM_INFO_FILE"] = os.environ.get(
    "AGENT_LLM_INFO_FILE",
    os.path.join(BASE_DIR, "registries", "llm_config.hocon"),
)
# Ensure the React build exists so the dashboard can render
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
MANIFEST_PATH = os.path.join(STATIC_DIR, "manifest.json")
if not os.path.exists(MANIFEST_PATH):
    logger.warning(
        "Frontend manifest missing at %s; run `npm --prefix apps/legal_discovery run build` before starting the server.",
        MANIFEST_PATH,
    )
    BUNDLE_NAME = "bundle.js"
else:
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    BUNDLE_NAME = manifest.get("src/main.jsx", {}).get("file", "bundle.js")
app = Flask(__name__)
metrics.init_app(app)
init_tracing(app)
config_path = os.environ.get("LEGAL_DISCOVERY_CONFIG")
secret_key = os.environ.get("FLASK_SECRET_KEY")
jwt_secret = os.environ.get("JWT_SECRET")
if config_path and (not secret_key or not jwt_secret):
    cfg = ConfigFactory.parse_file(config_path)
    secret_key = secret_key or cfg.get("flask.secret_key", None)
    jwt_secret = jwt_secret or cfg.get("flask.jwt_secret", None)
if not secret_key:
    secret_key = secrets.token_hex(32)
    logger.warning("FLASK_SECRET_KEY not set; using ephemeral value")
if not jwt_secret:
    logger.warning("JWT authentication disabled")
    jwt_secret = ""
app.config["SECRET_KEY"] = secret_key
app.config["JWT_SECRET"] = jwt_secret
# Configure rate limiting storage (Redis in production).
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get("REDIS_URL", "memory://")
# Attach a request ID to each request for tracing and log correlation.
@app.before_request
def _assign_request_id():
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    g.request_id = rid


@app.after_request
def _add_request_id_header(resp: Response):
    rid = getattr(g, "request_id", None)
    if rid:
        resp.headers["X-Request-ID"] = rid
    return resp

# --- Upload status tracking (Redis-backed with in-memory fallback) ----------
UPLOAD_STATUS: dict[str, dict] = {}


def _status_key(job_id: str) -> str:
    return f"upload:{job_id}"


def _status_set(job_id: str | None, data: dict) -> None:
    if not job_id:
        return
    try:
        if redis_client is not None:
            redis_client.set(_status_key(job_id), json.dumps(data), ex=86400)
            return
    except Exception:
        pass
    UPLOAD_STATUS[job_id] = data


def _status_get(job_id: str) -> dict | None:
    try:
        if redis_client is not None:
            raw = redis_client.get(_status_key(job_id))
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    return None
    except Exception:
        pass
    return UPLOAD_STATUS.get(job_id)


def _set_status(job_id: str | None, state: str, **kwargs) -> None:
    if not job_id:
        return
    payload = {"state": state, "updated": time.time()} | kwargs
    _status_set(job_id, payload)
    # Broadcast progress to connected clients
    try:  # pragma: no cover - best effort
        socketio.emit(
            "upload_progress",
            {"job_id": job_id, **payload},
            namespace="/ws/upload",
        )
    except Exception:
        pass
# Allow the primary relational store to be configured at runtime. Default to
# SQLite for local development but override with an environment-provided
# PostgreSQL connection string when available so the application scales under
# concurrent load.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///legal_discovery.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
socketio.init_app(app)
limiter.init_app(app)
with app.app_context():
    db.create_all()
    if not Case.query.first():
        default_case = Case(name="Default Case")
        db.session.add(default_case)
        db.session.commit()
    db_flags = settings.get_feature_flags()
    if db_flags:
        for k, v in db_flags.items():
            FEATURE_FLAGS[k] = bool(v)
app.register_blueprint(exhibits_bp)
app.register_blueprint(trial_prep_bp)
app.register_blueprint(trial_assistant_bp)
app.register_blueprint(hippo_bp)
app.register_blueprint(objections_bp)
app.register_blueprint(health_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(docs_bp)
if FEATURE_FLAGS.get("theories"):
    from .theory_routes import theories_bp

    app.register_blueprint(theories_bp)
if FEATURE_FLAGS.get("binder"):
    from .binder_routes import binder_bp

    app.register_blueprint(binder_bp)
if FEATURE_FLAGS.get("chat"):
    from .chat_routes import chat_bp

    app.register_blueprint(chat_bp)
executor = ThreadPoolExecutor(max_workers=int(os.environ.get("INGESTION_WORKERS", "4")))
atexit.register(executor.shutdown)
thread_started = False  # pylint: disable=invalid-name


@app.errorhandler(429)
def rate_limit_handler(exc):
    """Increment blocked request metrics and return a JSON error."""
    with tracer.start_as_current_span("rate_limit_handler"):
        endpoint = request.endpoint or request.path
        blocked_requests[endpoint] += 1
        return err("rate_limited", "rate limit exceeded"), 429


@app.errorhandler(404)
def not_found_handler(exc):
    return err("not_found", "resource not found"), 404


@app.errorhandler(400)
def bad_request_handler(exc):
    return err("bad_request", "invalid request"), 400


@app.errorhandler(500)
def internal_error_handler(exc):
    return err("internal_error", "unexpected server error"), 500


# Shared crawler instance for legal references
legal_crawler = LegalCrawler()

app.logger.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")))

# Shared agent session and worker thread are initialized asynchronously
legal_discovery_session = None
legal_discovery_thread = None


def _gather_upload_paths() -> list[str]:
    """Return a list of all files currently uploaded."""
    root = os.path.abspath("uploads")
    paths = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            paths.append(os.path.join(dirpath, fname))
    return paths


def _initialize_agent() -> None:
    """Set up the legal discovery assistant in a background thread."""
    global legal_discovery_session, legal_discovery_thread
    with app.app_context():
        app.logger.info("Setting up legal discovery assistant...")
        legal_discovery_session, legal_discovery_thread = set_up_legal_discovery_assistant(_gather_upload_paths())
        app.logger.info("...legal discovery assistant set up.")


threading.Thread(target=_initialize_agent, daemon=True).start()


def reinitialize_legal_discovery_session() -> None:
    """Reload the agent session with the latest uploaded files."""
    global legal_discovery_session, legal_discovery_thread
    if legal_discovery_session is not None:
        tear_down_legal_discovery_assistant(legal_discovery_session)
    legal_discovery_session, legal_discovery_thread = set_up_legal_discovery_assistant(_gather_upload_paths())
    app.logger.info("Legal discovery session reinitialized")


def legal_discovery_thinking_process():
    """Main permanent agent-calling loop."""
    with app.app_context():  # Manually push the application context
        global legal_discovery_thread  # pylint: disable=global-statement
        thoughts = "thought: hmm, let's see now..."
        while True:
            socketio.sleep(1)
            if legal_discovery_session is None:
                continue

            app.logger.debug("Calling legal_discovery_thinker...")
            thoughts, legal_discovery_thread = legal_discovery_thinker(
                legal_discovery_session, legal_discovery_thread, thoughts
            )
            app.logger.debug("...legal_discovery_thinker returned.")
            app.logger.debug(thoughts)

            # Separating thoughts and speeches
            # Assume 'thoughts' is the string returned by legal_discovery_thinker

            thoughts_to_emit = []
            speeches_to_emit = []

            # --- 1.  Slice the input into blocks ----------------------------------------
            #     Each block begins with  "thought:"  or  "say:"  and continues until
            #     the next block or the end of the string.
            pattern = re.compile(
                r"(?m)^(thought|say):[ \t]*(.*?)(?=^\s*(?:thought|say):|\Z)", re.S  # look-ahead  # dot = newline
            )

            for kind, raw in pattern.findall(thoughts):
                content = raw.lstrip()  # drop the leading spaces/newline after the prefix
                if not content:
                    continue

                if kind == "thought":
                    timestamp = datetime.now().strftime("[%I:%M:%S%p]").lower()
                    thoughts_to_emit.append(f"{timestamp} thought: {content}")
                else:  # kind == "say"
                    speeches_to_emit.append(content)

            # --- 2.  Emit the blocks -----------------------------------------------------
            if thoughts_to_emit:
                socketio.emit(
                    "update_thoughts",
                    {"data": "\n".join(thoughts_to_emit)},
                    namespace="/chat",
                )

            if speeches_to_emit:
                socketio.emit(
                    "update_speech",
                    {"data": "\n".join(speeches_to_emit)},
                    namespace="/chat",
                )

            timestamp = datetime.now().strftime("[%I:%M:%S%p]").lower()
            thoughts = f"\n{timestamp} user: " + "[Silence]"
            try:
                user_input = user_input_queue.get(timeout=0.1)
                if user_input:
                    thoughts = f"\n{timestamp} user: " + user_input
                if user_input == "exit":
                    break
            except queue.Empty:
                time.sleep(0.1)
                continue


@socketio.on("connect", namespace="/chat")
def on_connect():
    """Start background task on connect."""
    global thread_started  # pylint: disable=global-statement
    if not thread_started:
        thread_started = True
        # let socketio manage the green-thread
        socketio.start_background_task(legal_discovery_thinking_process)


@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    if request.method == "POST":
        data = request.get_json() or {}
        settings.save_user_settings(data)
        flags = {
            k: data[k]
            for k in [
                "voice_stt",
                "voice_tts",
                "voice_commands",
                "theories",
                "binder",
                "chat",
            ]
            if k in data
        }
        if flags:
            settings.save_feature_flags(flags)
            env_map = {
                "theories": "ENABLE_THEORIES",
                "binder": "ENABLE_BINDER",
                "chat": "ENABLE_CHAT",
                "voice_stt": "ENABLE_VOICE_STT",
                "voice_tts": "ENABLE_VOICE_TTS",
                "voice_commands": "ENABLE_VOICE_COMMANDS",
            }
            for flag, value in flags.items():
                FEATURE_FLAGS[flag] = bool(value)
                env_var = env_map.get(flag)
                if env_var:
                    os.environ[env_var] = "1" if value else "0"
        return jsonify({"message": "Settings saved successfully"})
    else:
        user_settings = settings.get_user_settings()
        resp = {}
        if user_settings:
            resp = {
                "courtlistener_api_key": user_settings.courtlistener_api_key,
                "courtlistener_com_api_endpoint": user_settings.courtlistener_com_api_endpoint,
                "california_codes_url": user_settings.california_codes_url,
                "gemini_api_key": user_settings.gemini_api_key,
                "google_api_endpoint": user_settings.google_api_endpoint,
                "verifypdf_api_key": user_settings.verifypdf_api_key,
                "verify_pdf_endpoint": user_settings.verify_pdf_endpoint,
                "riza_key": user_settings.riza_key,
                "neo4j_uri": user_settings.neo4j_uri,
                "neo4j_username": user_settings.neo4j_username,
                "neo4j_password": user_settings.neo4j_password,
                "neo4j_database": user_settings.neo4j_database,
                "aura_instance_id": user_settings.aura_instance_id,
                "aura_instance_name": user_settings.aura_instance_name,
                "gcp_project_id": user_settings.gcp_project_id,
                "gcp_vertex_ai_data_store_id": user_settings.gcp_vertex_ai_data_store_id,
                "gcp_vertex_ai_search_app": user_settings.gcp_vertex_ai_search_app,
                "gcp_service_account_key": user_settings.gcp_service_account_key,
                "theme": user_settings.theme,
            }
        flags = settings.get_feature_flags()
        for key in FEATURE_FLAGS:
            flags.setdefault(key, FEATURE_FLAGS[key])
        resp.update(flags)
        return jsonify(resp)


@app.route("/api/settings/api-keys", methods=["GET", "POST"])
def manage_api_keys():
    """Manage extended API key settings."""
    return manage_settings()


@app.route("/api/feature-flags", methods=["GET", "POST"])
def manage_feature_flags():
    if request.method == "POST":
        data = request.get_json() or {}
        settings.save_feature_flags(data)
        env_map = {
            "theories": "ENABLE_THEORIES",
            "binder": "ENABLE_BINDER",
            "chat": "ENABLE_CHAT",
            "voice_stt": "ENABLE_VOICE_STT",
            "voice_tts": "ENABLE_VOICE_TTS",
            "voice_commands": "ENABLE_VOICE_COMMANDS",
        }
        for flag, value in data.items():
            FEATURE_FLAGS[flag] = bool(value)
            env_var = env_map.get(flag)
            if env_var:
                os.environ[env_var] = "1" if value else "0"
        return jsonify({"message": "Flags updated"})
    flags = settings.get_feature_flags()
    for key in FEATURE_FLAGS:
        flags.setdefault(key, FEATURE_FLAGS[key])
    return jsonify(flags)


import shutil

from flask import send_from_directory

from coded_tools.legal_discovery.document_drafter import DocumentDrafter
from coded_tools.legal_discovery.document_modifier import DocumentModifier
from coded_tools.legal_discovery.document_processor import DocumentProcessor
from coded_tools.legal_discovery.fact_extractor import FactExtractor
from coded_tools.legal_discovery.forensic_tools import ForensicTools
from coded_tools.legal_discovery.graph_analyzer import GraphAnalyzer
from coded_tools.legal_discovery.knowledge_graph_manager import KnowledgeGraphManager
from coded_tools.legal_discovery.ontology_loader import OntologyLoader
from coded_tools.legal_discovery.presentation_generator import PresentationGenerator
from coded_tools.legal_discovery.privilege_detector import PrivilegeDetector
from coded_tools.legal_discovery.research_tools import ResearchTools
from coded_tools.legal_discovery.subpoena_manager import SubpoenaManager
from coded_tools.legal_discovery.task_tracker import TaskTracker
from coded_tools.legal_discovery.timeline_manager import TimelineManager
from coded_tools.legal_discovery.auto_drafter import AutoDrafter
from coded_tools.legal_discovery.vector_database_manager import VectorDatabaseManager
from coded_tools.legal_discovery.document_scorer import DocumentScorer
from coded_tools.legal_discovery.sanctions_risk_analyzer import SanctionsRiskAnalyzer

# Allow hosting the corpus on an attached volume via UPLOAD_ROOT
UPLOAD_FOLDER = os.environ.get("UPLOAD_ROOT", os.path.join(BASE_DIR, "uploads"))
SECURE_FOLDER = os.path.join(UPLOAD_FOLDER, "_original")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SECURE_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SECURE_FOLDER"] = SECURE_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "txt", "csv", "doc", "docx", "ppt", "pptx", "jpg", "jpeg", "png", "gif"}
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB

# Singleton task tracker instance for quick task management
task_tracker = TaskTracker()


def allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def unique_filename(filename: str) -> str:
    """Return a filesystem-safe name that does not overwrite existing uploads."""
    base_dir = app.config["UPLOAD_FOLDER"]
    name, ext = os.path.splitext(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(base_dir, candidate)):
        candidate = f"{name}_{counter}{ext}"
        counter += 1
    return candidate


def chunked(items: list, size: int) -> list[list]:
    """Yield successive ``size``-sized chunks from ``items``."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


_NLP = None


def match_elements(text: str, ontology: dict) -> list[tuple[str, str, float]]:
    """Return (cause, element, weight) triples whose semantics appear in ``text``."""
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:  # pragma: no cover - model download is slow
            spacy_download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm")

    doc = _NLP(text.lower())
    text_lemmas = {t.lemma_ for t in doc if not t.is_stop and t.is_alpha}
    matches: list[tuple[str, str, float]] = []
    for cause, data in ontology.get("causes_of_action", {}).items():
        for element in data.get("elements", []):
            elem_doc = _NLP(element.lower())
            elem_lemmas = {t.lemma_ for t in elem_doc if not t.is_stop and t.is_alpha}
            if not elem_lemmas:
                continue
            overlap = text_lemmas & elem_lemmas
            jaccard = len(overlap) / len(elem_lemmas)
            seq_ratio = SequenceMatcher(None, text.lower(), element.lower()).ratio()
            weight = 0.7 * seq_ratio + 0.3 * jaccard
            if weight >= 0.45:
                matches.append((cause, element, weight))
    return matches


def build_file_tree(directory: str, root_length: int, docs: dict[str, Document]) -> list:
    """Recursively build a file tree structure."""
    tree = []
    for entry in os.scandir(directory):
        if entry.name.startswith("_"):
            continue
        rel_path = entry.path[root_length:].lstrip(os.sep)
        node = {"path": rel_path, "name": entry.name}
        doc = docs.get(rel_path)
        if doc:
            node["privileged"] = doc.is_privileged
            node["id"] = doc.id
            node["source"] = doc.source.value
            node["sha256"] = doc.sha256
        if entry.is_dir():
            node["children"] = build_file_tree(entry.path, root_length, docs)
        tree.append(node)
    return sorted(tree, key=lambda x: (not x.get("children"), x["name"]))


@app.route("/api/files", methods=["GET"])
def list_files():
    """Return a hierarchical view of uploaded files."""
    root = os.path.abspath(app.config["UPLOAD_FOLDER"])
    if not os.path.exists(root):
        return jsonify({"status": "ok", "data": []})
    docs = {os.path.relpath(doc.file_path, root): doc for doc in Document.query.all()}
    data = build_file_tree(root, len(root), docs)
    return jsonify({"status": "ok", "data": data})


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """Return scored document listings."""
    docs = Document.query.all()
    data = [
        {
            "id": d.id,
            "name": d.name,
            "probative_value": d.probative_value or 0,
            "admissibility_risk": d.admissibility_risk or 0,
            "narrative_alignment": d.narrative_alignment or 0,
            "score_confidence": d.score_confidence or 0,
        }
        for d in docs
    ]
    return jsonify({"status": "ok", "data": data})


@app.route("/api/redaction/<int:doc_id>", methods=["POST"])
def review_redaction(doc_id: int):
    """Confirm or override a document's redaction status."""
    data = request.get_json() or {}
    action = data.get("action")
    reason = data.get("reason")
    reviewer = data.get("reviewer")
    doc = Document.query.get_or_404(doc_id)
    if action == "override":
        doc.is_privileged = False
        doc.is_redacted = False
        doc.needs_review = False
        orig = os.path.join(app.config["SECURE_FOLDER"], doc.name)
        try:
            shutil.copy(orig, doc.file_path)
        except OSError as exc:
            logger.exception("failed to restore original file", exc_info=exc)
            return jsonify({"error": "Failed to restore original document"}), 500
    elif action == "confirm":
        doc.needs_review = False
    else:
        return jsonify({"error": "Invalid action"}), 400
    db.session.add(RedactionAudit(document_id=doc.id, reviewer=reviewer, action=action, reason=reason))
    db.session.commit()
    return jsonify({"status": "ok"})


@app.route("/api/privilege/<int:doc_id>", methods=["POST"])
def override_privilege(doc_id: int):
    """Manually override a document's privilege flag."""
    data = request.get_json() or {}
    privileged = data.get("privileged")
    reviewer = data.get("reviewer")
    reason = data.get("reason")
    if privileged is None:
        return jsonify({"error": "privileged required"}), 400
    doc = Document.query.get_or_404(doc_id)
    doc.is_privileged = bool(privileged)
    doc.is_redacted = bool(privileged)
    doc.needs_review = False
    app.logger.info(
        "override privilege",
        extra={"doc_id": doc.id, "privileged": doc.is_privileged, "reviewer": reviewer},
    )
    db.session.add(
        RedactionAudit(
            document_id=doc.id,
            reviewer=reviewer,
            action="override_privilege",
            reason=reason,
        )
    )
    log_event(
        doc.id,
        ChainEventType.REDACTED,
        metadata={"override": True, "privileged": doc.is_privileged},
        source_team="legal_discovery",
    )
    db.session.commit()
    return jsonify({"status": "ok", "privileged": doc.is_privileged})


@app.route("/api/agents", methods=["GET"])
def list_agents():
    """Return agent team names from the legal discovery registry."""
    config_path = os.path.join(BASE_DIR, "registries", "legal_discovery.hocon")
    cfg = ConfigFactory.parse_file(config_path)
    orchestrator = cfg.get("tools")[0]
    agents = [{"name": name} for name in orchestrator.get("tools", [])]
    return jsonify({"status": "ok", "data": agents})


@app.route("/api/topics", methods=["GET"])
def list_topics():
    """Return distinct legal theory topics from the database."""
    case_id = request.args.get("case_id")
    query = LegalTheory.query
    if case_id:
        query = query.filter_by(case_id=case_id)
    topics = query.with_entities(LegalTheory.theory_name).distinct().all()
    data = [{"label": name} for (name,) in topics]
    return jsonify({"status": "ok", "data": data})


@app.route("/api/calendar", methods=["GET", "POST", "DELETE"])
def calendar_events():
    """Manage calendar events for a case."""
    if request.method == "POST":
        data = request.get_json() or {}
        case_id = data.get("case_id")
        date = data.get("date")
        title = data.get("title")
        if not case_id or not date or not title:
            return jsonify({"error": "Missing case_id, date or title"}), 400
        event = CalendarEvent(
            case_id=case_id,
            title=title,
            event_date=datetime.fromisoformat(date),
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({"status": "ok", "id": event.id})

    if request.method == "DELETE":
        data = request.get_json() or {}
        event_id = data.get("id")
        if not event_id:
            return jsonify({"error": "Missing id"}), 400
        event = CalendarEvent.query.get(event_id)
        if not event:
            return jsonify({"error": "Event not found"}), 404
        db.session.delete(event)
        db.session.commit()
        return jsonify({"status": "ok"})

    case_id = request.args.get("case_id")
    if not case_id:
        return jsonify({"status": "ok", "data": []})
    events = CalendarEvent.query.filter_by(case_id=case_id).order_by(CalendarEvent.event_date).all()
    data = [{"id": e.id, "date": e.event_date.strftime("%Y-%m-%d"), "title": e.title} for e in events]
    return jsonify({"status": "ok", "data": data})


def _collect_paths(root: str) -> list:
    paths = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            paths.append(os.path.relpath(os.path.join(dirpath, f), root))
    return paths


def _categorize_name(name: str) -> str:
    name = name.lower()
    if any(k in name for k in ["complaint", "response", "petition"]):
        return "Pleadings"
    if "deposition" in name:
        return "Depositions"
    if any(k in name for k in ["contract", "agreement"]):
        return "Contracts"
    if "email" in name:
        return "Emails"
    if any(k in name for k in ["memo", "memorandum"]):
        return "Memos"
    return "Other"


def _paths_to_tree(entries: list[dict]) -> list:
    tree = {}
    for e in entries:
        p, src = e["path"], e.get("source")
        parts = p.split(os.sep)
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("_files", []).append((parts[-1], src))

    def convert(d, prefix=""):
        items = []
        for name, val in sorted(d.items()):
            if name == "_files":
                for fname, src in val:
                    items.append({"name": fname, "path": os.path.join(prefix, fname), "source": src})
            else:
                items.append(
                    {
                        "name": name,
                        "path": os.path.join(prefix, name),
                        "children": convert(val, os.path.join(prefix, name)),
                    }
                )
        return items

    return convert(tree)


@app.route("/api/organized-files", methods=["GET"])
def organized_files():
    """Return files grouped into simple categories."""
    root = os.path.abspath(app.config["UPLOAD_FOLDER"])
    if not os.path.exists(root):
        return jsonify({"status": "ok", "data": {}})

    files = _collect_paths(root)
    docs = {os.path.relpath(doc.file_path, root): doc.source.value for doc in Document.query.all()}
    categories: dict[str, list[dict]] = {}
    for path in files:
        cat = _categorize_name(os.path.basename(path))
        categories.setdefault(cat, []).append({"path": path, "source": docs.get(path)})

    data = {cat: _paths_to_tree(entries) for cat, entries in categories.items()}
    return jsonify({"status": "ok", "data": data})


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Serve a file from the uploads folder."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)


def cleanup_upload_folder(max_age_hours: int = 24) -> None:
    """Remove uploaded files older than ``max_age_hours``."""
    cutoff = time.time() - max_age_hours * 3600
    for root_dir, _, files in os.walk(app.config["UPLOAD_FOLDER"]):
        for name in files:
            path = os.path.join(root_dir, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except FileNotFoundError:
                continue


def update_legal_references() -> None:
    """Crawl legal sources and update the graph."""
    refs = legal_crawler.crawl_all()
    legal_crawler.store(refs)


def ingest_document(
    original_path: str,
    redacted_path: str,
    doc_id: int,
    case_id: int,
    full_metadata: dict,
    chroma_metadata: dict,
    job_id: str | None = None,
    enable_redaction: bool = False,
) -> None:
    """Extract, vectorize, and relate a document in the background."""
    with app.app_context():
        _set_status(job_id, "started", doc_id=doc_id)
        processor = DocumentProcessor()
        text = processor.extract_text(original_path) or ""
        detector = PrivilegeDetector()
        privileged, spans = detector.detect(text)
        app.logger.info(
            "privilege detection",
            extra={"doc_id": doc_id, "privileged": privileged, "spans": [(s.start, s.end) for s in spans]},
        )
        doc = Document.query.get(doc_id)
        if doc is None:
            app.logger.error("Document %s not found during ingestion", doc_id)
            raise LookupError(f"Document {doc_id} not found")
            return
        if enable_redaction and privileged:
            keywords = [text[s.start : s.end] for s in spans]
            if original_path.lower().endswith(".pdf"):
                detector.redact_pdf(original_path, redacted_path, keywords)
                redacted_text = processor.extract_text(redacted_path) or ""
            else:
                redacted_text = detector.redact_text(text, spans)
                with open(redacted_path, "w", encoding="utf-8") as f:
                    f.write(redacted_text)
            doc.is_privileged = True
            doc.is_redacted = True
            doc.needs_review = True
            for s in spans:
                db.session.add(
                    RedactionLog(
                        document_id=doc_id,
                        start=s.start,
                        end=s.end,
                        label=s.label,
                        reason=(f"{s.text} (score={s.score:.2f})" if s.score is not None else s.text),
                    )
                )
            db.session.commit()
            _set_status(job_id, "redacted")
            log_event(
                doc_id,
                ChainEventType.REDACTED,
                metadata={"spans": [(s.start, s.end) for s in spans]},
                source_team="legal_discovery",
            )
        else:
            shutil.copy(original_path, redacted_path)
            redacted_text = text
            # When redaction is disabled, do not mark as privileged/redacted.
            if enable_redaction:
                doc.is_privileged = False
                doc.is_redacted = False
                doc.needs_review = False
            db.session.commit()
            _set_status(job_id, "extracted")

        scorer = DocumentScorer()
        scores = scorer.score(redacted_text)
        doc.probative_value = scores["probative_value"]
        doc.admissibility_risk = scores["admissibility_risk"]
        doc.narrative_alignment = scores["narrative_alignment"]
        doc.score_confidence = scores["score_confidence"]
        db.session.add(DocumentMetadata(document_id=doc_id, schema="evidence_scorecard", data=scores))
        try:
            sanctions = SanctionsRiskAnalyzer().assess(redacted_text, scorecard=scores)
            db.session.add(DocumentMetadata(document_id=doc_id, schema="sanctions_risk", data=sanctions))
        except Exception as exc:
            logger.exception("sanctions risk analysis failed", exc_info=exc)
        db.session.commit()

        # Chunk text and add to Chroma in batches for robustness
        def _chunk_text(t: str, max_chars: int = 4000, overlap: int = 400) -> list[str]:
            t = t or ""
            parts: list[str] = []
            if len(t) <= max_chars:
                return [t] if t else []
            start = 0
            while start < len(t):
                end = min(start + max_chars, len(t))
                parts.append(t[start:end])
                if end == len(t):
                    break
                start = max(0, end - overlap)
            return [p for p in parts if p.strip()]

        chunks = _chunk_text(redacted_text)
        if not chunks:
            chunks = [redacted_text]
        total = len(chunks)
        ids = [f"{doc_id}:{i}" for i in range(total)]
        md = []
        for i in range(total):
            m = dict(chroma_metadata)
            m.update({"chunk": i, "n_chunks": total})
            md.append(m)
        vdm = VectorDatabaseManager()
        vdm.add_documents_batched(chunks, md, ids, batch_size=256)
        _set_status(job_id, "vectored", chunks=total)
        kg = KnowledgeGraphManager()
        result = kg.run_query("MERGE (c:Case {id: $id}) RETURN id(c) as cid", {"id": case_id})
        case_node = result[0]["cid"] if result else None
        doc_node = kg.create_node("Document", full_metadata)
        if case_node:
            kg.create_relationship(case_node, doc_node, "HAS_DOCUMENT")

        extractor = FactExtractor()
        ontology = OntologyLoader().load()
        for fact in extractor.extract(redacted_text):
            fact_row = Fact(
                case_id=case_id,
                document_id=doc_id,
                text=fact["text"],
                parties=fact["parties"],
                dates=fact["dates"],
                actions=fact["actions"],
            )
            db.session.add(fact_row)
            matches = match_elements(fact["text"], ontology)
            if matches:
                cause_name, element_name = matches[0]
                element_row = (
                    Element.query.join(CauseOfAction)
                    .filter(
                        CauseOfAction.name == cause_name,
                        Element.name == element_name,
                    )
                    .first()
                )
                if element_row:
                    fact_row.element_id = element_row.id
            fact_id = None
            if case_node or doc_node:
                fact_id = kg.add_fact(case_node, doc_node, fact)
            if fact_id is not None:
                for cause, element in matches:
                    kg.link_fact_to_element(fact_id, cause, element)
                for cause, element, weight in match_elements(fact["text"], ontology):
                    kg.link_fact_to_element(fact_id, cause, element, weight)

        kg.close()
        log_event(
            doc_id,
            ChainEventType.INGESTED,
            metadata={"path": redacted_path},
            source_team="legal_discovery",
        )
        _set_status(job_id, "done")


MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TIMEOUT = 30  # seconds per file


@app.route("/api/upload", methods=["POST"])
def upload_files():
    upload_root = app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_root, exist_ok=True)
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    source_str = request.form.get("source", "user").lower()
    redaction_flag = (request.form.get("redaction", "false").lower() == "true")
    try:
        source_enum = DocumentSource(source_str)
    except ValueError:
        return jsonify({"error": "Invalid source"}), 400

    accepted, skipped = [], []
    case = Case.query.first()
    case_id = case.id if case else 1

    def record_skip(name, reason):
        skipped.append(name)
        app.logger.warning(f"[SKIP] {name} — {reason}")
        with open("skipped_files.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {name} — {reason}\n")

    for batch_index, batch in enumerate([files[i : i + 10] for i in range(0, len(files), 10)]):
        app.logger.info(f"Starting batch {batch_index + 1}")
        batch_processed: list[str] = []
        futures: list[tuple] = []

        for file in batch:
            raw_name = os.path.normpath(file.filename)
            if not raw_name or not allowed_file(raw_name):
                record_skip(raw_name, "disallowed or blank filename")
                continue

            if getattr(file, "content_length", None) and file.content_length > MAX_FILE_SIZE:
                record_skip(raw_name, "file too large")
                continue

            hasher, total_read = hashlib.sha256(), 0
            start_time = time.time()
            try:
                for chunk in iter(lambda: file.stream.read(8192), b""):
                    hasher.update(chunk)
                    total_read += len(chunk)
                    if time.time() - start_time > MAX_TIMEOUT or total_read > MAX_FILE_SIZE:
                        raise TimeoutError("Exceeded time/size limit during hash")
                file.stream.seek(0)
            except Exception as exc:
                record_skip(raw_name, f"hashing error: {exc}")
                continue

            file_hash = hasher.hexdigest()
            if Document.query.filter_by(sha256=file_hash).first():
                record_skip(raw_name, "duplicate hash")
                continue

            filename = unique_filename(raw_name)
            redacted_path = os.path.join(upload_root, filename)
            original_path = os.path.join(app.config["SECURE_FOLDER"], filename)
            os.makedirs(os.path.dirname(original_path), exist_ok=True)
            os.makedirs(os.path.dirname(redacted_path), exist_ok=True)
            try:
                file.save(original_path)
            except Exception as exc:
                record_skip(raw_name, f"save error: {exc}")
                continue

            doc = Document(
                case_id=case_id,
                name=filename,
                file_path=redacted_path,
                sha256=file_hash,
                source=source_enum,
            )
            db.session.add(doc)
            db.session.flush()

            full_metadata = {
                "filename": filename,
                "path": redacted_path,
                "original_path": original_path,
                "case_id": case_id,
                "document_id": str(doc.id),
                "sha256": file_hash,
                "upload_time": str(time.time()),
                "source": source_str,
            }
            chroma_metadata = {k: str(v) for k, v in full_metadata.items() if isinstance(v, (str, int, float, bool))}

            with open(redacted_path + ".meta.json", "w") as f:
                json.dump(full_metadata, f, indent=2)

            raw_meta = DocumentMetadata(document_id=doc.id, schema="raw", data=full_metadata)
            chroma_meta = DocumentMetadata(document_id=doc.id, schema="chroma", data=chroma_metadata)
            db.session.add_all([raw_meta, chroma_meta])
            # Ensure the document and metadata are committed so the background
            # ingestion thread can retrieve them using a separate session.
            db.session.commit()
            # Enqueue background ingestion and return job ID immediately
            job_id = uuid.uuid4().hex
            _set_status(job_id, "queued", filename=filename, doc_id=int(doc.id))
            future = executor.submit(
                ingest_document,
                original_path,
                redacted_path,
                doc.id,
                case_id,
                full_metadata,
                chroma_metadata,
                job_id,
                redaction_flag,
            )
            futures.append((future, job_id, filename))
            accepted.append(job_id)

        # Do not block on futures; return job IDs to the client
    return ok({"accepted": accepted, "skipped": skipped}, status=202)


@app.route("/api/upload/status", methods=["GET"])
def upload_status():
    """Return ingestion status for one or more job IDs.

    Accepts repeated `job_id` query params or a comma-separated list in `job_id`.
    """
    ids = request.args.getlist("job_id")
    if len(ids) == 1 and "," in ids[0]:
        ids = [i.strip() for i in ids[0].split(",") if i.strip()]
    if not ids:
        return err("bad_request", "job_id is required"), 400
    payload = {}
    for jid in ids:
        st = _status_get(jid)
        payload[jid] = st or {"state": "unknown"}
    return ok(payload)

        try:
            db.session.commit()
        except Exception as exc:  # pragma: no cover - best effort
            db.session.rollback()
            app.logger.error("Batch commit failed: %s", exc)

        VectorDatabaseManager().persist()

        if batch_processed:
            reinitialize_legal_discovery_session()
            user_input_queue.put(
                "process all files ingested within your scope and produce a basic overview and report."
            )

    return jsonify({"status": "ok", "processed": processed, "skipped": skipped})


@app.route("/api/export", methods=["GET"])
def export_files():
    archive = "processed_files.zip"
    shutil.make_archive("processed_files", "zip", UPLOAD_FOLDER)
    for doc in Document.query.all():
        log_event(
            doc.id,
            ChainEventType.EXPORTED,
            metadata={"archive": archive},
            source_team="legal_discovery",
        )
    return send_from_directory(".", archive, as_attachment=True)


@app.route("/api/chain", methods=["GET"])
def get_chain_log():
    doc_id = request.args.get("document_id", type=int)
    if not doc_id:
        return jsonify({"error": "Missing document_id"}), 400
    entries = ChainOfCustodyLog.query.filter_by(document_id=doc_id).order_by(ChainOfCustodyLog.timestamp).all()
    return jsonify(
        {
            "document_id": doc_id,
            "events": [
                {
                    "type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "user_id": e.user_id,
                    "metadata": e.event_metadata,
                    "signature_hash": e.signature_hash,
                }
                for e in entries
            ],
        }
    )


@app.route("/api/narrative_discrepancies", methods=["GET"])
def list_narrative_discrepancies():
    """Return stored narrative discrepancies."""
    case_id = request.args.get("case_id", type=int)
    query = NarrativeDiscrepancy.query
    if case_id:
        query = query.join(Document, NarrativeDiscrepancy.opposing_doc_id == Document.id).filter(
            Document.case_id == case_id
        )
    records = query.order_by(NarrativeDiscrepancy.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": r.id,
                "opposing_doc_id": r.opposing_doc_id,
                "user_doc_id": r.user_doc_id,
                "conflicting_claim": r.conflicting_claim,
                "evidence_excerpt": r.evidence_excerpt,
                "confidence": r.confidence,
                "legal_theory_id": r.legal_theory_id,
                "calendar_event_id": r.calendar_event_id,
            }
            for r in records
        ]
    )


@app.route("/api/narrative_discrepancies/analyze", methods=["POST"])
def analyze_narrative_discrepancy():
    """Analyze an opposition document for discrepancies."""
    data = request.get_json(force=True) or {}
    try:
        payload = NarrativeDiscrepancyAnalyzePayload.model_validate(data)
    except ValidationError as e:
        return jsonify({"errors": e.errors()}), 400
    doc = Document.query.get_or_404(payload.opposing_doc_id)
    detector = NarrativeDiscrepancyDetector()
    results = detector.analyze(doc)
    return jsonify([r.__dict__ for r in results])


@app.route("/api/narrative_discrepancies/export", methods=["GET"])
def export_narrative_discrepancies():
    fmt = request.args.get("format", "csv").lower()
    records = NarrativeDiscrepancy.query.all()
    if fmt == "pdf":
        rows = [
            f"<tr><td>{r.conflicting_claim}</td><td>{r.evidence_excerpt}</td><td>{r.confidence:.2f}</td></tr>"
            for r in records
        ]
        html = "<table><tr><th>Claim</th><th>Evidence</th><th>Confidence</th></tr>" + "".join(rows) + "</table>"
        pdf = HTML(string=html).write_pdf()
        return send_file(
            BytesIO(pdf),
            as_attachment=True,
            download_name="narrative_discrepancies.pdf",
            mimetype="application/pdf",
        )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["conflicting_claim", "evidence_excerpt", "confidence"])
    for r in records:
        writer.writerow([r.conflicting_claim, r.evidence_excerpt, r.confidence])
    return send_file(
        BytesIO(output.getvalue().encode("utf-8")),
        as_attachment=True,
        download_name="narrative_discrepancies.csv",
        mimetype="text/csv",
    )


@app.route("/api/agents/forensic_analysis", methods=["POST"])
def forensic_analysis():
    data = request.get_json()
    file_path = data.get("file_path")
    analysis_type = data.get("analysis_type")

    if not file_path or not analysis_type:
        return jsonify({"error": "Missing file_path or analysis_type"}), 400

    forensic_tools = ForensicTools()

    if analysis_type == "authenticity":
        result = forensic_tools.analyze_document_authenticity(file_path)
    elif analysis_type == "financial":
        result = forensic_tools.financial_forensics(file_path)
    else:
        return jsonify({"error": "Invalid analysis_type"}), 400

    return jsonify({"result": result})


@app.route("/api/forensic/logs", methods=["GET"])
def forensic_logs():
    """Return forensic analysis logs if available."""
    log_path = os.path.join(app.config["UPLOAD_FOLDER"], "forensic.log")
    if not os.path.exists(log_path):
        return jsonify({"status": "ok", "data": []})
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    return jsonify({"status": "ok", "data": lines})


@app.route("/api/document/redact", methods=["POST"])
def redact_document():
    """Redact occurrences of text in a PDF using DocumentModifier."""
    data = request.get_json() or {}
    file_path = data.get("file_path")
    text = data.get("text")
    if not file_path or not text:
        return jsonify({"error": "Missing file_path or text"}), 400

    modifier = DocumentModifier()
    try:
        modifier.redact_text(file_path, text)
    except Exception as exc:  # pragma: no cover - filesystem errors
        return jsonify({"error": str(exc)}), 500
    doc = Document.query.filter_by(file_path=file_path).first()
    if doc:
        log_event(
            doc.id,
            ChainEventType.REDACTED,
            metadata={"text": text},
            source_team="legal_discovery",
        )
    return jsonify({"message": "File redacted", "output": f"{file_path}_redacted.pdf"})


@app.route("/api/document/stamp", methods=["POST"])
def bates_stamp_document():
    """Apply Bates numbering to a PDF and record a new version."""
    data = request.get_json() or {}
    file_path = data.get("file_path")
    prefix = data.get("prefix", "BATES")
    user_id = data.get("user_id")
    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400
    doc = Document.query.filter_by(file_path=file_path).first()
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    # Determine next Bates number and stamp the PDF
    start = bates_service.get_next_bates_number(prefix)
    start_num = int(start.split("_")[-1])
    # Advance counter for remaining pages
    page_total = fitz.open(file_path).page_count
    for _ in range(page_total - 1):
        bates_service.get_next_bates_number(prefix)
    output_path = f"{file_path}_v{start}.pdf"
    try:
        stamp_pdf(file_path, output_path, start_num, prefix=prefix)
    except Exception as exc:  # pragma: no cover - filesystem errors
        return jsonify({"error": str(exc)}), 500
    doc.bates_number = start
    version = DocumentVersion(
        document_id=doc.id,
        version_number=DocumentVersion.query.filter_by(document_id=doc.id).count() + 1,
        bates_number=start,
        user_id=user_id,
        file_path=output_path,
    )
    db.session.add(version)
    db.session.commit()
    log_event(
        doc.id,
        ChainEventType.STAMPED,
        metadata={"prefix": prefix},
        source_team="legal_discovery",
    )
    log_event(
        doc.id,
        ChainEventType.VERSIONED,
        metadata={"version_id": version.id, "bates_number": start},
        source_team="legal_discovery",
    )
    return jsonify({"message": "File stamped", "output": output_path, "bates_number": start})


@app.route("/api/document/versions")
def document_versions():
    """Return version history for a document."""
    file_path = request.args.get("file_path")
    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400
    doc = Document.query.filter_by(file_path=file_path).first()
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    versions = DocumentVersion.query.filter_by(document_id=doc.id).order_by(DocumentVersion.timestamp).all()
    results = []
    for v in versions:
        user = Agent.query.get(v.user_id) if v.user_id else None
        results.append(
            {
                "id": v.id,
                "bates_number": v.bates_number,
                "user": user.name if user else None,
                "timestamp": v.timestamp.isoformat(),
            }
        )
    return jsonify(results)


from flask import request, jsonify
import difflib


@app.route("/api/document/versions/diff")
def document_versions_diff():
    """Compute a unified diff between two document versions."""
    v1_id = request.args.get("v1")
    v2_id = request.args.get("v2")

    if not v1_id or not v2_id:
        return jsonify({"error": "Missing version ids"}), 400

    v1 = DocumentVersion.query.get(v1_id)
    v2 = DocumentVersion.query.get(v2_id)

    if not v1 or not v2:
        return jsonify({"error": "Version not found"}), 404

    processor = DocumentProcessor()
    text1 = processor.extract_text(v1.file_path)
    text2 = processor.extract_text(v2.file_path)

    diff_lines = difflib.unified_diff(
        text1.splitlines(),
        text2.splitlines(),
        fromfile=v1.bates_number or "version_1",
        tofile=v2.bates_number or "version_2",
        lineterm="",
    )

    return jsonify({"diff": "\n".join(diff_lines)})


@app.route("/api/bates/stamp", methods=["POST"])
def bates_stamp():
    """Apply Bates numbering to a PDF and record a document version."""
    data = request.get_json() or {}
    file_path = data.get("file_path")
    prefix = data.get("prefix", "BATES")
    document_id = data.get("document_id")
    user_id = data.get("user_id")
    if not file_path or document_id is None or user_id is None:
        return (
            jsonify({"error": "file_path, document_id and user_id required"}),
            400,
        )
    start_bates = bates_service.get_next_bates_number(prefix)
    start_number = int(start_bates.split("_")[-1])
    output_path = f"{file_path}_stamped.pdf"
    try:
        stamp_pdf(file_path, output_path, start_number, prefix=prefix)
    except Exception as exc:  # pragma: no cover - filesystem errors
        return jsonify({"error": str(exc)}), 500
    last_version = (
        DocumentVersion.query.filter_by(document_id=document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    version_number = 1 if last_version is None else last_version.version_number + 1
    version = DocumentVersion(
        document_id=document_id,
        version_number=version_number,
        file_path=output_path,
        bates_number=start_bates,
        user_id=user_id,
    )
    db.session.add(version)
    doc = Document.query.get(document_id)
    if doc:
        log_event(
            doc.id,
            ChainEventType.STAMPED,
            user_id=user_id,
            metadata={"prefix": prefix, "version": version_number},
            source_team="legal_discovery",
        )
    db.session.commit()
    return jsonify(
        {
            "message": "File stamped",
            "output": output_path,
            "bates": start_bates,
            "version": version_number,
        }
    )


@app.route("/api/document/<int:doc_id>/versions", methods=["GET"])
def get_document_versions(doc_id: int):
    """Return version history for a document."""
    versions = DocumentVersion.query.filter_by(document_id=doc_id).order_by(DocumentVersion.version_number).all()
    return jsonify(
        {
            "versions": [
                {
                    "version": v.version_number,
                    "bates_number": v.bates_number,
                    "user": v.user.name if getattr(v, "user", None) else v.user_id,
                    "timestamp": v.created_at.isoformat(),
                }
                for v in versions
            ]
        }
    )


def _extract_text(path: str) -> str:
    doc = fitz.open(path)
    return "\n".join(page.get_text() for page in doc)


@app.route("/api/document/<int:doc_id>/diff", methods=["GET"])
def diff_document_versions(doc_id: int):
    """Return unified diff between two document versions."""
    try:
        from_v = int(request.args.get("from"))
        to_v = int(request.args.get("to"))
    except (TypeError, ValueError):
        return jsonify({"error": "from and to parameters required"}), 400
    v1 = DocumentVersion.query.filter_by(document_id=doc_id, version_number=from_v).first_or_404()
    v2 = DocumentVersion.query.filter_by(document_id=doc_id, version_number=to_v).first_or_404()
    text1 = _extract_text(v1.file_path)
    text2 = _extract_text(v2.file_path)
    diff = "".join(
        difflib.unified_diff(
            text1.splitlines(),
            text2.splitlines(),
            fromfile=f"v{from_v}",
            tofile=f"v{to_v}",
            lineterm="",
        )
    )
    return jsonify({"diff": diff})


@app.route("/api/document/draft", methods=["POST"])
def draft_document():
    """Create or update a DOCX document using DocumentDrafter."""
    data = request.get_json() or {}
    filepath = data.get("filepath")
    content = data.get("content", "")
    action = data.get("action", "create")
    level = int(data.get("level", 1))
    if not filepath:
        return jsonify({"error": "Missing filepath"}), 400
    drafter = DocumentDrafter()
    try:
        if action == "paragraph":
            drafter.add_paragraph(filepath, content)
        elif action == "heading":
            drafter.add_heading(filepath, content, level)
        else:
            drafter.create_document(filepath, content)
    except Exception as exc:  # pragma: no cover - file system errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "output": filepath})


@app.route("/api/auto_draft/templates")
def auto_draft_templates():
    """Return available motion templates."""
    drafter = AutoDrafter()
    return jsonify({"data": drafter.templates.available()})


@app.route("/api/auto_draft", methods=["POST"])
def auto_draft_generate():
    """Generate a motion draft using Gemini 2.5."""
    data = request.get_json() or {}
    motion_type = data.get("motion_type")
    if not motion_type:
        return jsonify({"error": "Missing motion_type"}), 400
    drafter = AutoDrafter()
    try:
        draft = drafter.generate(motion_type)
    except Exception as exc:  # pragma: no cover - LLM errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"data": draft})


@app.route("/api/auto_draft/export", methods=["POST"])
def auto_draft_export():
    """Export reviewed draft to DOCX or PDF."""
    data = request.get_json() or {}
    content = data.get("content", "")
    fmt = data.get("format", "docx").lower()
    if not content:
        return jsonify({"error": "Missing content"}), 400
    filename = f"draft_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{fmt}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    drafter = AutoDrafter()
    try:
        drafter.export(content, path, fmt)
    except Exception as exc:  # pragma: no cover - file errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "output": filename})


@app.route("/api/vector/add", methods=["POST"])
def vector_add_documents():
    """Add documents to the vector database."""
    data = request.get_json() or {}
    documents = data.get("documents")
    ids = data.get("ids")
    if not documents or not ids:
        return jsonify({"error": "Missing documents or ids"}), 400
    metadatas = data.get("metadatas") or [{"source": "api"} for _ in documents]
    metadatas = [md if md else {"source": "api"} for md in metadatas]
    if len(metadatas) != len(documents):
        return jsonify({"error": "Invalid metadata length"}), 400
    manager = VectorDatabaseManager()
    manager.add_documents(documents, metadatas, ids)
    invalidate_prefix("vector_search")
    invalidate_prefix("hippo_query")
    return jsonify({"status": "ok"})


@redis_cache("vector_search", key_func=lambda q: q)
def _vector_search_cached(q: str):
    manager = VectorDatabaseManager()
    return manager.query([q], n_results=5)


@app.route("/api/vector/search", methods=["GET"])
def vector_search():
    """Query the vector database."""
    query = request.args.get("q")
    if not query:
        return ok({})
    result = _vector_search_cached(query)
    return ok(result)


@app.route("/api/vector/count", methods=["GET"])
def vector_count():
    """Return the document count in the vector database."""
    manager = VectorDatabaseManager()
    count = manager.get_document_count()
    return ok(count)


@app.route("/api/cocounsel/search", methods=["GET"])
def cocounsel_search():
    """Search legal references for CoCounsel."""
    query = request.args.get("q", "")
    results = legal_crawler.kg.search_legal_references(query) if query else []
    return jsonify(results)


@app.route("/api/drafter/search", methods=["GET"])
def drafter_search():
    """Search legal references for the auto-drafter."""
    query = request.args.get("q", "")
    results = legal_crawler.kg.search_legal_references(query) if query else []
    return jsonify(results)


@app.route("/api/document/text", methods=["POST"])
def extract_document_text():
    """Extract text from a document using DocumentProcessor."""
    data = request.get_json() or {}
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400
    processor = DocumentProcessor()
    try:
        text = processor.extract_text(file_path)
    except Exception as exc:  # pragma: no cover - filesystem errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "data": text})


@app.route("/api/tasks", methods=["GET", "POST", "DELETE"])
def manage_tasks():
    """Simple task tracker endpoints."""
    if request.method == "POST":
        data = request.get_json() or {}
        task = data.get("task")
        if not task:
            return jsonify({"error": "Missing task"}), 400
        msg = task_tracker.add_task(task)
        return jsonify({"status": "ok", "message": msg})
    if request.method == "DELETE":
        msg = task_tracker.clear_tasks()
        return jsonify({"status": "ok", "message": msg})

    tasks = task_tracker.list_tasks()
    return jsonify({"status": "ok", "data": tasks})


@app.route("/api/cases", methods=["GET", "POST", "DELETE"])
def manage_cases():
    """List, create or delete cases."""
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "Missing name"}), 400
        case = Case(name=name)
        db.session.add(case)
        db.session.commit()
        return jsonify({"status": "ok", "id": case.id})

    if request.method == "DELETE":
        data = request.get_json() or {}
        case_id = data.get("id")
        if not case_id:
            return jsonify({"error": "Missing id"}), 400
        case = Case.query.get(case_id)
        if not case:
            return jsonify({"error": "Case not found"}), 404
        Document.query.filter_by(case_id=case_id).delete()
        TimelineEvent.query.filter_by(case_id=case_id).delete()
        LegalReference.query.filter_by(case_id=case_id).delete()
        db.session.delete(case)
        db.session.commit()
        return jsonify({"status": "ok"})

    cases = Case.query.all()
    data = [{"id": c.id, "name": c.name} for c in cases]
    return jsonify({"status": "ok", "data": data})


@app.route("/api/witnesses", methods=["GET", "POST"])
def manage_witnesses():
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name")
        case_id = data.get("case_id")
        if not name:
            return jsonify({"error": "Missing name"}), 400
        witness = Witness(name=name, role=data.get("role"), associated_case=case_id)
        db.session.add(witness)
        db.session.commit()
        return jsonify({"status": "ok", "id": witness.id})
    case_id = request.args.get("case_id", type=int)
    query = Witness.query
    if case_id:
        query = query.filter_by(associated_case=case_id)
    witnesses = query.all()
    data = [{"id": w.id, "name": w.name} for w in witnesses]
    return jsonify({"status": "ok", "data": data})


@app.route("/api/deposition/questions", methods=["POST"])
def generate_deposition_questions():
    data = request.get_json() or {}
    witness_id = data.get("witness_id")
    include_privileged = data.get("include_privileged", False)
    if not witness_id:
        return jsonify({"error": "Missing witness_id"}), 400
    questions = DepositionPrep.generate_questions(witness_id, include_privileged=include_privileged)
    questions = DepositionPrep.generate_questions(witness_id, include_privileged=include_privileged)
    return jsonify({"status": "ok", "data": questions})


@app.route("/api/deposition/questions/<int:question_id>/flag", methods=["POST"])
def flag_deposition_question(question_id: int):
    DepositionPrep.flag_question(question_id)
    return jsonify({"status": "ok"})


@app.route("/api/deposition/export/<int:witness_id>", methods=["GET"])
def export_deposition_questions(witness_id: int):
    fmt = request.args.get("format", "docx")
    reviewer_id = request.args.get("reviewer_id", type=int)
    if not reviewer_id:
        return jsonify({"error": "Missing reviewer_id"}), 400
    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", f"deposition_{witness_id}.{fmt}")
    try:
        DepositionPrep.export_questions(witness_id, path, reviewer_id)
    except PermissionError:
        return jsonify({"error": "Forbidden"}), 403
    return send_file(path, as_attachment=True)


@app.route("/api/deposition/review", methods=["POST"])
def review_deposition():
    data = request.get_json() or {}
    witness_id = data.get("witness_id")
    reviewer_id = data.get("reviewer_id")
    approved = data.get("approved", False)
    notes = data.get("notes")
    if not witness_id or not reviewer_id:
        return jsonify({"error": "Missing witness_id or reviewer_id"}), 400
    try:
        DepositionPrep.log_review(witness_id, reviewer_id, approved, notes)
    except PermissionError:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"status": "ok"})


@app.route("/api/subpoena/draft", methods=["POST"])
def draft_subpoena():
    """Draft a subpoena document using SubpoenaManager."""
    data = request.get_json() or {}
    file_path = data.get("file_path")
    content = data.get("content")
    if not file_path or not content:
        return jsonify({"error": "Missing file_path or content"}), 400
    mgr = SubpoenaManager()
    try:
        mgr.draft_subpoena_document(file_path, content)
    except Exception as exc:  # pragma: no cover - file system errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "output": file_path})


@app.route("/api/presentation", methods=["POST"])
def create_presentation():
    """Create or update a PowerPoint presentation."""
    data = request.get_json() or {}
    filepath = data.get("filepath")
    slides = data.get("slides", [])
    if not filepath or not isinstance(slides, list):
        return jsonify({"error": "Missing filepath or slides"}), 400
    gen = PresentationGenerator()
    try:
        gen.create_presentation(filepath)
        for slide in slides:
            title = slide.get("title", "")
            content = slide.get("content", "")
            gen.add_slide(filepath, title, content)
    except Exception as exc:  # pragma: no cover - file system errors
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "output": filepath})


@app.route("/api/progress", methods=["GET"])
def progress_status():
    """Return basic progress metrics."""
    root = app.config["UPLOAD_FOLDER"]
    upload_count = 0
    if os.path.exists(root):
        upload_count = sum(len(f) for _, _, f in os.walk(root))
    data = {"uploaded_files": upload_count}
    return jsonify({"status": "ok", "data": data})


@app.route("/api/metrics", methods=["GET"])
def aggregated_metrics():
    """Return combined counts for dashboard metrics."""
    root = app.config["UPLOAD_FOLDER"]
    upload_count = 0
    if os.path.exists(root):
        upload_count = sum(len(f) for _, _, f in os.walk(root))

    vector_count = 0
    try:
        vector_count = VectorDatabaseManager().get_document_count()
    except Exception:  # pragma: no cover - optional dependency may fail
        vector_count = 0

    graph_count = 0
    try:
        kg_manager = KnowledgeGraphManager()
        result = kg_manager.run_query("MATCH (n) RETURN count(n) AS count")
        graph_count = result[0]["count"] if result else 0
        kg_manager.close()
    except Exception:  # pragma: no cover - database may be unavailable
        graph_count = 0

    task_count = len(task_tracker.list_tasks())

    case_count = Case.query.count()

    log_path = os.path.join(root, "forensic.log")
    log_count = 0
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            log_count = len(f.read().splitlines())

    data = {
        "uploaded_files": upload_count,
        "vector_docs": vector_count,
        "graph_nodes": graph_count,
        "task_count": task_count,
        "forensic_logs": log_count,
        "case_count": case_count,
    }
    return jsonify({"status": "ok", "data": data})


@app.route("/api/neo4j/health", methods=["GET"])
def neo4j_health():
    try:
        kg = KnowledgeGraphManager()
        ok = kg.run_query("RETURN 1 AS ok")
        kg.close()
        return jsonify({"status": "ok", "driver": ok[0]["ok"]}), 200
    except Exception as exc:  # pragma: no cover - connection may fail
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.route("/api/graph/export", methods=["GET"])
def export_graph():
    kg_manager = KnowledgeGraphManager()
    output_path = kg_manager.export_graph()
    kg_manager.close()
    return send_from_directory(".", output_path, as_attachment=False)


@app.route("/api/graph", methods=["GET"])
def get_graph():
    subnet = request.args.get("subnet", "")
    kg_manager = KnowledgeGraphManager()
    try:
        nodes, edges = kg_manager.get_subgraph(subnet) if subnet else kg_manager.get_subgraph("*")
    except Exception:
        nodes, edges = [], []
    kg_manager.close()
    return jsonify({"status": "ok", "data": {"nodes": nodes, "edges": edges}})


@app.route("/api/graph/analyze", methods=["GET"])
def analyze_graph():
    """Return centrality analysis of the knowledge graph."""
    subnet = request.args.get("subnet", "*")
    analyzer = GraphAnalyzer()
    try:
        results = analyzer.analyze_centrality(subnet)
        user_input_queue.put("Provide insights on the most connected entities in the case graph.")
    except Exception as exc:  # pragma: no cover - optional analysis may fail
        app.logger.error("Graph analysis failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok", "data": results})


@app.route("/api/graph/cypher", methods=["POST"])
def run_cypher_query():
    """Execute an arbitrary Cypher query against the knowledge graph."""
    data = request.get_json(force=True) or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "missing query"}), 400
    kg = KnowledgeGraphManager()
    try:
        results = kg.run_query(query)
    except Exception as exc:  # pragma: no cover - user queries may fail
        kg.close()
        return jsonify({"error": str(exc)}), 400
    kg.close()
    return jsonify({"status": "ok", "data": results})


def _get_file_excerpt(case_id: str, length: int = 400) -> str | None:
    """Return a short excerpt from the first document for the case."""
    doc = Document.query.filter_by(case_id=case_id).first()
    if not doc or not doc.file_path:
        return None
    try:
        with open(doc.file_path, "r", errors="ignore") as f:
            return f.read(length)
    except Exception:  # pragma: no cover - optional file may be missing
        return None


@app.route("/api/timeline/export", methods=["POST"])
def export_timeline():
    data = request.get_json()
    timeline_id = data.get("timeline_id")

    if not timeline_id:
        return jsonify({"error": "Missing timeline_id"}), 400

    timeline_manager = TimelineManager()
    events = TimelineEvent.query.filter_by(case_id=timeline_id).order_by(TimelineEvent.event_date).all()

    timeline_items = []
    for event in events:
        citation = None
        ref = LegalReference.query.filter_by(case_id=event.case_id).first()
        if ref:
            citation = ref.source_url
        excerpt = _get_file_excerpt(event.case_id)
        timeline_items.append(
            {
                "content": event.description,
                "start": event.event_date.strftime("%Y-%m-%d"),
                "citation": citation,
                "excerpt": excerpt,
            }
        )

    html = timeline_manager.render_timeline(timeline_items)
    timeline_manager.close()
    return html


@app.route("/api/timeline", methods=["GET"])
def get_timeline():
    query = request.args.get("query")
    if not query:
        return jsonify({"status": "ok", "data": []})

    events = TimelineEvent.query.filter_by(case_id=query).order_by(TimelineEvent.event_date).all()

    data = []
    for event in events:
        citation = None
        ref = LegalReference.query.filter_by(case_id=event.case_id).first()
        if ref:
            citation = ref.source_url
        excerpt = _get_file_excerpt(event.case_id)
        data.append(
            {
                "id": event.id,
                "date": event.event_date.strftime("%Y-%m-%d"),
                "description": event.description,
                "citation": citation,
                "excerpt": excerpt,
                "links": event.links or {},
            }
        )

    return jsonify({"status": "ok", "data": data})


@app.route("/api/timeline/summary", methods=["GET"])
def timeline_summary():
    case_id = request.args.get("case_id", type=int)
    tm = TimelineManager()
    return jsonify({"status": "ok", "summary": tm.summarize(case_id)})


@app.route("/api/research", methods=["GET"])
def research():
    query = request.args.get("query")
    source = request.args.get("source", "all")
    tool = ResearchTools()
    results = tool.search(query, source) if query else []
    return jsonify({"status": "ok", "data": results})


@app.route("/api/export/report", methods=["POST"])
def export_report():
    data = request.get_json() or {}
    rpt_type = data.get("type")
    if rpt_type == "timeline":
        return export_timeline()
    elif rpt_type == "files":
        return export_files()
    elif rpt_type == "graph":
        return export_graph()
    else:
        return jsonify({"error": "Invalid type"}), 400


@app.route("/present/<mode>/<doc_id>")
def present(mode: str, doc_id: str):
    """Render the document viewer for live presentations."""
    return render_template("dashboard.html", bundle_js=BUNDLE_NAME)


@app.route("/")
def index():
    """Serve the React dashboard by default."""
    return render_template("dashboard.html", bundle_js=BUNDLE_NAME)


@app.route("/dashboard")
def dashboard():
    """Return the dashboard UI."""
    return render_template("dashboard.html", bundle_js=BUNDLE_NAME)


@socketio.on("user_input", namespace="/chat")
def handle_user_input(json, *_):
    """
    Handles user input.

    :param json: A json object
    """
    user_input = json["data"]
    user_input_queue.put(user_input)
    socketio.emit("update_user_input", {"data": user_input}, namespace="/chat")


def cleanup():
    """Tear things down on exit."""
    app.logger.info("Bye!")
    if legal_discovery_session is not None:
        tear_down_legal_discovery_assistant(legal_discovery_session)
    socketio.stop()


@app.route("/shutdown")
def shutdown():
    """Shut down process."""
    cleanup()
    return "Capture ended"


@app.after_request
def add_header(response):
    """Add the header."""
    response.headers["Cache-Control"] = "no-store"
    return response


def run_scheduled_tasks():
    """Run the scheduled tasks."""
    while True:
        schedule.run_pending()
        time.sleep(1)


# Register the cleanup function
atexit.register(cleanup)

# Setup and start scheduled maintenance tasks
schedule.every().day.at("01:00").do(update_legal_references)
schedule.every().day.at("00:00").do(cleanup_upload_folder)
socketio.start_background_task(run_scheduled_tasks)

if __name__ == "__main__":
    app.logger.info("Starting Flask server...")
    with app.app_context():
        db.create_all()
    socketio.run(
        app,
        debug=False,
        host="0.0.0.0",
        port=5001,
        allow_unsafe_werkzeug=True,
        log_output=True,
        use_reloader=False,
    )
