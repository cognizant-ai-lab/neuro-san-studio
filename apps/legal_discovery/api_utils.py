from __future__ import annotations

from typing import Any, Dict, Optional

from flask import jsonify


def ok(data: Any = None, meta: Optional[Dict[str, Any]] = None, status: int = 200):
    payload: Dict[str, Any] = {"ok": True}
    if data is not None:
        payload["data"] = data
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status


def err(code: str, message: str, details: Optional[Dict[str, Any]] = None, status: int = 400):
    payload: Dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status

