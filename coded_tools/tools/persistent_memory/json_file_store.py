# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""
JSON-file implementation of ``MemoryStore``.

One JSON file per topic, laid out as::

    <root_path>/<agent_network_name>/<agent_name>/<topic>.json

The file contains a single JSON object mapping entry keys to their value
dicts::

    {
        "name": {"content": "The user's name is Mike."},
        "favorite_coffee_order": {
            "content": "User prefers black coffee from Henry's.",
            "category": "drink"
        }
    }

Use this backend when another process (or a human via ``jq``) will read the
memory files — JSON is unambiguous and trivial to parse, at the cost of being
less pleasant to hand-edit than the markdown backend.

Shared filesystem machinery (locking, atomic writes, path resolution) lives in
``MemoryStore``; this module only owns the JSON serialisation format.
"""

import json
import logging
from typing import Any

from coded_tools.tools.persistent_memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class JsonFileStore(MemoryStore):
    """
    One-JSON-file-per-topic store backend.

    :param root_path: Directory under which all topic files live.
                      Created on first write if it does not exist.
    """

    _EXTENSION: str = "json"

    def _serialise(self, entries: dict[str, dict[str, Any]]) -> str:
        return json.dumps(entries, ensure_ascii=False, indent=2, sort_keys=True)

    def _deserialise(self, content: str) -> dict[str, dict[str, Any]]:
        if not content.strip():
            return {}
        try:
            parsed: Any = json.loads(content)
        except json.JSONDecodeError as error:
            logger.warning("JsonFileStore: malformed JSON (%s). Treating as empty.", error)
            return {}
        if not isinstance(parsed, dict):
            logger.warning(
                "JsonFileStore: top-level JSON is %s, expected object. Ignoring.",
                type(parsed).__name__,
            )
            return {}
        result: dict[str, dict[str, Any]] = {}
        for key, value in parsed.items():
            if isinstance(value, dict):
                result[str(key)] = value
            else:
                # Tolerate raw strings by coercing into the ``{"content": ...}``
                # shape so a hand-edited ``{"name": "Mike"}`` still loads.
                result[str(key)] = {"content": str(value)}
        return result
