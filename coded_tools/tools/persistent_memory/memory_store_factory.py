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
Backend factory for persistent-memory stores.

Lives in its own module so the base ABC and the concrete backends (which
import the ABC) do not form a cycle — the factory sits above both and is
the only place that imports every concrete subclass.
"""

import logging
from typing import Any
from typing import Optional

from coded_tools.tools.persistent_memory.base_memory_store import BaseMemoryStore
from coded_tools.tools.persistent_memory.base_memory_store import MemoryStoreConfig
from coded_tools.tools.persistent_memory.json_file_store import JsonFileStoreBackend
from coded_tools.tools.persistent_memory.md_file_store import MdFileStoreBackend

logger = logging.getLogger(__name__)

# Backend identifiers exposed as constants rather than stringly-typed.
BACKEND_FILE_SYSTEM: str = "file_system"
BACKEND_JSON_FILE: str = "json_file"

VALID_BACKENDS: frozenset[str] = frozenset(
    {
        BACKEND_FILE_SYSTEM,
        BACKEND_JSON_FILE,
    }
)


def resolve_config(tool_config_store: Optional[dict[str, Any]] = None) -> MemoryStoreConfig:
    """
    Build a ``MemoryStoreConfig`` by layering env overrides on top of HOCON.

    See :py:meth:`MemoryStoreConfig.resolve` for the precedence rules.

    :param tool_config_store: ``store_config`` dict from HOCON. ``None`` or
                              ``{}`` yields a config populated purely from env.
    :return: A populated config.
    """
    return MemoryStoreConfig.resolve(tool_config_store)


def create_store(tool_config_store: Optional[dict[str, Any]] = None) -> BaseMemoryStore:
    """
    Build and return the backend selected by the resolved config.

    :param tool_config_store: ``store_config`` dict from HOCON.
    :return: A ready-to-use ``BaseMemoryStore`` subclass instance.
    :raises ValueError: If the backend name is not recognised.
    """
    config: MemoryStoreConfig = resolve_config(tool_config_store)
    backend: str = (config.backend or "").strip().lower()

    if backend not in VALID_BACKENDS:
        raise ValueError(f"Unknown memory backend '{config.backend}'. Valid options: {sorted(VALID_BACKENDS)}.")

    logger.info(
        "Creating memory store backend: %s (root_path=%s)",
        backend,
        config.root_path,
    )

    if backend == BACKEND_FILE_SYSTEM:
        return MdFileStoreBackend(root_path=config.root_path)

    # json_file — only backend left.
    return JsonFileStoreBackend(root_path=config.root_path)
