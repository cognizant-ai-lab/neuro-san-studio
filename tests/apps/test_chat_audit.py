import base64
import os
import pytest

os.environ["DATABASE_URL"] = "sqlite://"

from apps.legal_discovery.interface_flask import app, db, MessageAuditLog


@pytest.fixture
def client():
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app.test_client()


def test_query_logs_message(client):
    resp = client.post("/api/chat/query", json={"text": "hello"})
    assert resp.status_code == 200
    with app.app_context():
        logs = MessageAuditLog.query.all()
        assert any(l.sender == "user" and l.transcript == "hello" for l in logs)


def test_voice_query_logs_message(client, monkeypatch):
    monkeypatch.setattr(
        "apps.legal_discovery.voice.synthesize_voice", lambda text, model: ""
    )
    audio = base64.b64encode(b"test").decode()
    resp = client.post(
        "/api/chat/voice",
        json={"audio": audio, "transcript": "hi", "voice_model": "en-US"},
    )
    assert resp.status_code == 200
    with app.app_context():
        log = MessageAuditLog.query.filter_by(transcript="hi").first()
        assert log is not None
        assert log.voice_model == "en-US"


def test_voice_command_executes_and_logs(client, monkeypatch):
    monkeypatch.setattr("apps.legal_discovery.voice.synthesize_voice", lambda text, model: "")
    monkeypatch.setattr("coded_tools.legal_discovery.chat_agent.RetrievalChatAgent.query", lambda self, question, sender_id=0, conversation_id=None: {"message_id": "1", "facts": []})
    called = {}
    from apps.legal_discovery import voice_commands
    def dummy(data):
        called["hit"] = True
        return "done"
    monkeypatch.setattr(voice_commands, "COMMAND_REGISTRY", {"dummy": dummy})
    resp = client.post("/api/chat/voice", json={"transcript": "dummy action", "voice_model": "en-US"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["command"] == "dummy"
    assert data["result"] == "done"
    assert called.get("hit")
    with app.app_context():
        log = MessageAuditLog.query.filter_by(sender="command").first()
        assert log is not None
        assert log.transcript == "dummy"
