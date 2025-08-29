from flask import Blueprint, jsonify, request

from coded_tools.legal_discovery.chat_agent import RetrievalChatAgent
from coded_tools.legal_discovery.timeline_manager import TimelineManager

from .database import db
from .models import MessageAuditLog
from .extensions import socketio, limiter, user_limit_key
from .chat_state import user_input_queue
from .voice import synthesize_voice, get_available_voices
from .feature_flags import FEATURE_FLAGS
from .stt import stream_transcribe
from .voice_commands import execute_command
from .auth import auth_required, _require_auth

import base64
import os
import logging

from apps.message_bus import (
    AUTO_DRAFTER_ALERT_TOPIC,
    TIMELINE_ALERT_TOPIC,
    MessageBus,
    TeamMessage,
)


chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

bus = MessageBus()
_listeners_started = False


def _ensure_listeners_started() -> None:
    """Subscribe cross-team services to message bus events."""
    global _listeners_started  # pylint: disable=global-statement
    if _listeners_started:
        return
    try:
        from apps.legal_discovery import listener as ld_listener
        from apps.conscious_assistant import listener as ca_listener
        from apps.wwaw import listener as ww_listener
        from apps.cruse import listener as cr_listener
        from apps.log_analyzer import listener as la_listener

        ld_listener.start_listening()
        ca_listener.start_listening()
        ww_listener.start_listening()
        cr_listener.start_listening()
        la_listener.start_listening()
        _listeners_started = True
    except Exception as exc:  # pragma: no cover - network/services optional
        logging.warning("Listener startup failed: %s", exc)


def _publish_alert(topic: str, payload: dict) -> None:
    """Publish a TeamMessage and log it for audit."""
    bus.publish(topic, TeamMessage("voice", payload))
    logging.info("Cross-team alert on %s: %s", topic, payload)


def _handle_transcript(transcript: str, data: dict) -> dict:
    """Common handler for processing a user transcript."""
    user_input_queue.put(transcript)
    agent = RetrievalChatAgent()
    result = agent.query(
        question=transcript,
        sender_id=data.get("sender_id", 0),
        conversation_id=data.get("conversation_id"),
    )
    if not result.get("conversation_id"):
        from .models import Message

        msg = Message.query.get(result.get("message_id"))
        if msg:
            result["conversation_id"] = msg.conversation_id
    response_text = result.get("answer") or "\n".join(result.get("facts", []))
    if response_text:
        socketio.emit("update_speech", {"data": response_text}, namespace="/chat")
        if FEATURE_FLAGS["voice_tts"]:
            audio = synthesize_voice(response_text, data.get("voice_model", "en-US"))
            socketio.emit("voice_output", {"audio": audio}, namespace="/chat")
        db.session.add(
            MessageAuditLog(
                message_id=result["message_id"],
                sender="assistant",
                transcript=response_text,
                voice_model=data.get("voice_model"),
            )
        )
    db.session.add(
        MessageAuditLog(
            message_id=result["message_id"],
            sender="user",
            transcript=transcript,
            voice_model=data.get("voice_model"),
        )
    )
    db.session.commit()
    return {
        "status": "ok",
        "message_id": result["message_id"],
        "conversation_id": result.get("conversation_id"),
    }

@chat_bp.post("/query")
@limiter.limit("100/minute")
@limiter.limit("50/minute", key_func=user_limit_key)
@auth_required
def query_agent():
    data = request.get_json() or {}
    text = data.get("text")
    if not text:
        return jsonify({"status": "error", "error": "text required"}), 400
    tm = TimelineManager()
    case_id = data.get("case_id", 1)
    if text.lower().startswith("timeline summary"):
        return jsonify({"status": "ok", "summary": tm.summarize(case_id)})
    event = tm.upsert_event_from_text(text, case_id)
    if event:
        socketio.emit(
            "update_speech",
            {"data": f"Recorded event on {event['date']}"},
            namespace="/chat",
        )
    user_input_queue.put(text)
    agent = RetrievalChatAgent()
    result = agent.query(
        question=text,
        sender_id=data.get("sender_id", 0),
        conversation_id=data.get("conversation_id"),
    )
    if not result.get("conversation_id"):
        from .models import Message

        msg = Message.query.get(result.get("message_id"))
        if msg:
            result["conversation_id"] = msg.conversation_id
    response_text = result.get("answer") or "\n".join(result.get("facts", []))
    if response_text:
        socketio.emit("update_speech", {"data": response_text}, namespace="/chat")
        db.session.add(
            MessageAuditLog(
                message_id=result["message_id"],
                sender="assistant",
                transcript=response_text,
                voice_model=data.get("voice_model"),
            )
        )
    db.session.add(
        MessageAuditLog(
            message_id=result["message_id"],
            sender="user",
            transcript=text,
            voice_model=data.get("voice_model"),
        )
    )
    db.session.commit()
    return jsonify(
        {
            "status": "ok",
            "message_id": result["message_id"],
            "conversation_id": result.get("conversation_id"),
        }
    )


@chat_bp.post("/voice")
@limiter.limit("10/minute")
@auth_required
def voice_query():
    data = request.get_json() or {}
    transcript = data.get("transcript")
    if not transcript:
        return jsonify({"status": "error", "error": "transcript required"}), 400
    _ensure_listeners_started()
    case_id = data.get("case_id", 1)
    tm = TimelineManager()
    event = tm.upsert_event_from_text(transcript, case_id)
    if event:
        _publish_alert(TIMELINE_ALERT_TOPIC, {"case_id": case_id, "event": event})
    if "document" in transcript.lower():
        _publish_alert(AUTO_DRAFTER_ALERT_TOPIC, {"transcript": transcript})

    command = execute_command(transcript, data) if FEATURE_FLAGS["voice_commands"] else None
    if command:
        keyword, output = command
        if keyword.startswith("timeline"):
            _publish_alert(
                TIMELINE_ALERT_TOPIC, {"case_id": case_id, "command": keyword}
            )
        if "document" in keyword:
            _publish_alert(
                AUTO_DRAFTER_ALERT_TOPIC, {"command": keyword, "case_id": case_id}
            )
        result = _handle_transcript(transcript, data)
        db.session.add(
            MessageAuditLog(
                message_id=result["message_id"],
                sender="command",
                transcript=keyword,
                voice_model=data.get("voice_model"),
            )
        )
        db.session.commit()
        return jsonify(
            {
                "status": "ok",
                "command": keyword,
                "result": output,
                "message_id": result["message_id"],
            }
        )

    result = _handle_transcript(transcript, data)
    return jsonify(result)


@chat_bp.get("/voices")
@limiter.limit("10/minute")
@auth_required
def list_voices():
    if not FEATURE_FLAGS["voice_tts"]:
        return jsonify({"voices": []})
    return jsonify({"voices": get_available_voices()})


@chat_bp.post("/voice/settings")
@limiter.limit("10/minute")
@auth_required
def set_voice_settings():
    """Persist voice engine/model preferences."""
    data = request.get_json() or {}
    from . import settings as app_settings
    app_settings.save_user_settings({
        "voice_engine": data.get("voice_engine"),
        "voice_model": data.get("voice_model"),
    })
    if data.get("voice_engine"):
        os.environ["VOICE_ENGINE"] = str(data.get("voice_engine"))
    if data.get("voice_model"):
        os.environ["VOICE_MODEL"] = str(data.get("voice_model"))
    return jsonify({"status": "ok"})


@socketio.on("voice_query", namespace="/chat")
def voice_query_ws(data):
    """Handle streaming audio frames over WebSocket."""
    if not _require_auth():
        socketio.emit("voice_error", {"error": "unauthorized"}, namespace="/chat")
        return
    if not FEATURE_FLAGS["voice_stt"]:
        socketio.emit("voice_error", {"error": "stt_disabled"}, namespace="/chat")
        return
    frames = data.get("frames") or []
    if not frames:
        socketio.emit("voice_error", {"error": "no audio"}, namespace="/chat")
        return

    audio_iter = (base64.b64decode(f) for f in frames)
    final_text = ""
    for chunk in stream_transcribe(audio_iter):
        if chunk.get("error"):
            socketio.emit("voice_error", {"error": chunk["error"]}, namespace="/chat")
            return
        if chunk["is_final"]:
            final_text = chunk["text"]
        else:
            socketio.emit(
                "voice_transcript",
                {"text": chunk["text"], "final": False},
                namespace="/chat",
            )

    if not final_text:
        socketio.emit(
            "voice_error", {"error": "transcription_unavailable"}, namespace="/chat"
        )
        return

    socketio.emit(
        "voice_transcript", {"text": final_text, "final": True}, namespace="/chat"
    )
    result = _handle_transcript(final_text, data)
    return {"text": final_text, "conversation_id": result.get("conversation_id")}


__all__ = ["chat_bp"]
