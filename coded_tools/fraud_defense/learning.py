"""Explicit structured learning from predicted versus observed outcomes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List


class LearningStore:
    """Append-only local knowledge store; no uncontrolled self-modifying code."""

    def __init__(self, path: str | Path = "artifacts/fraud_learning.json"):
        self.path = Path(path)
        self.database_path = self.path.with_suffix(".sqlite3")

    def _connect(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("CREATE TABLE IF NOT EXISTS outcomes (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        return connection

    def record(self, case_id: str, attack_pattern: str, defense: Dict[str, Any], predicted: Dict[str, float], observed: Dict[str, float], failure_mode: str | None = None) -> Dict[str, Any]:
        """Calculate prediction error and append a reusable outcome record."""
        item = {
            "case_id": case_id,
            "attack_pattern": attack_pattern,
            "defense_id": defense.get("control_id"),
            "defense": defense.get("name"),
            "predicted": predicted,
            "observed": observed,
            "prediction_error": {key: round(float(predicted.get(key, 0)) - float(observed.get(key, 0)), 4) for key in set(predicted) | set(observed)},
            "failure_mode": failure_mode or ("false_positive_behavior" if observed.get("false_positive_rate", 0) > predicted.get("false_positive_rate", 0) else "none_observed"),
            "successful_defense": observed.get("fraud_prevented_rate", 0) >= predicted.get("fraud_prevented_rate", 0) * 0.9,
        }
        connection = self._connect()
        try:
            with connection:
                connection.execute("INSERT INTO outcomes(payload) VALUES (?)", (json.dumps(item, allow_nan=False),))
        finally:
            connection.close()
        return item

    def read(self) -> List[Dict[str, Any]]:
        """Read structured knowledge, tolerating a missing or malformed local file."""
        legacy = []
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, list):
                raise ValueError("Invalid legacy learning store; preserve and repair it before continuing")
            legacy = value
        if not self.database_path.exists():
            return legacy
        connection = self._connect()
        try:
            return legacy + [json.loads(row[0]) for row in connection.execute("SELECT payload FROM outcomes ORDER BY id")]
        finally:
            connection.close()
