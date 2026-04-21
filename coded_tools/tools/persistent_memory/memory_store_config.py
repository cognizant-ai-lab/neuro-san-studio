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
Configuration dataclass for memory store backends, with env-override resolution.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from dataclasses import fields
from typing import Any
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryStoreConfig:
    """
    Configuration for a memory store backend.

    :param backend:   Backend identifier. See ``VALID_BACKENDS`` in the factory.
    :param root_path: Root directory for file-based backends.
    """

    backend: str = "markdown_file"
    root_path: str = "./memory"

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "MemoryStoreConfig":
        """
        Build a ``MemoryStoreConfig`` from a plain dict, ignoring unknown keys.

        :param data: A dict read from HOCON ``tool_config`` or from a JSON env var.
                     ``None`` and ``{}`` both yield a default config.
        :return:     A populated ``MemoryStoreConfig``.
        """
        if not data:
            return cls()

        known_fields: set[str] = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in known_fields}
        return cls(**kwargs)

    @classmethod
    def resolve(cls, hocon_dict: Optional[dict[str, Any]]) -> "MemoryStoreConfig":
        """
        Resolve the final config by layering env overrides on top of HOCON.

        Precedence (later wins):
            1. ``hocon_dict`` — the ``store_config`` block read from HOCON.
            2. ``MEMORY_STORE_CONFIG`` — a JSON object env var, shallow-merged
               over the HOCON dict. Useful for swapping whole backends at
               deploy time without editing HOCON.
            3. Individual ``MEMORY_*`` env vars — field-level overrides. The
               most surgical layer; a single var can point the tool at a new
               Postgres URL or S3 bucket while everything else stays HOCON.
        """
        merged: dict[str, Any] = dict(hocon_dict or {})

        env_json: Optional[str] = os.environ.get("MEMORY_STORE_CONFIG")
        if env_json:
            try:
                parsed: Any = json.loads(env_json)
            except json.JSONDecodeError as error:
                logger.warning("MEMORY_STORE_CONFIG is not valid JSON; ignoring. (%s)", error)
            else:
                if isinstance(parsed, dict):
                    merged.update(parsed)
                else:
                    logger.warning(
                        "MEMORY_STORE_CONFIG must be a JSON object; got %s. Ignoring.",
                        type(parsed).__name__,
                    )

        # Individual vars win over MEMORY_STORE_CONFIG so a deployer can pin a
        # single field without rebuilding the whole JSON blob.
        env_field_map: dict[str, str] = {
            "MEMORY_BACKEND": "backend",
            "MEMORY_ROOT_PATH": "root_path",
        }
        for env_name, field_name in env_field_map.items():
            value: Optional[str] = os.environ.get(env_name)
            if value is not None and value != "":
                merged[field_name] = value

        return cls.from_dict(merged)
