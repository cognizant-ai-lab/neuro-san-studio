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

Backends are looked up in a class-level registry so downstream projects
can plug in new store implementations (Postgres, S3, Redis, …) without
forking this file — see :py:meth:`MemoryStoreFactory.register`.
"""

from __future__ import annotations

import logging
from typing import Any
from typing import Callable
from typing import Optional

from coded_tools.tools.persistent_memory.json_file_store import JsonFileStore
from coded_tools.tools.persistent_memory.markdown_file_store import MarkdownFileStore
from coded_tools.tools.persistent_memory.memory_store import MemoryStore
from coded_tools.tools.persistent_memory.memory_store_config import MemoryStoreConfig

logger = logging.getLogger(__name__)

# Callable that turns a resolved config into a concrete store. Kept as a
# module-level alias so the registry type is readable from both inside and
# outside the class.
BackendBuilder = Callable[[MemoryStoreConfig], MemoryStore]


class MemoryStoreFactory:
    """
    Registry-backed factory for :py:class:`MemoryStore` subclasses.

    Resolves a ``MemoryStoreConfig`` (HOCON + env overrides), looks the
    ``backend`` name up in :py:attr:`_REGISTRY`, and returns the built store.

    Adding a new backend from outside this module::

        MemoryStoreFactory.register(
            "postgres",
            lambda cfg: PostgresStoreBackend(url=cfg.root_path),
        )

    The registry is mutable on purpose — tests and downstream projects
    register their own backends at import time.
    """

    # Backend identifiers exposed as constants rather than stringly-typed.
    BACKEND_MARKDOWN_FILE: str = "markdown_file"
    BACKEND_JSON_FILE: str = "json_file"

    # name → builder. Populated with the built-in backends below the class
    # body so the builders can reference the concrete subclasses without
    # forward-reference gymnastics.
    _REGISTRY: dict[str, BackendBuilder] = {}

    @classmethod
    def register(cls, name: str, builder: BackendBuilder) -> None:
        """Register a new backend under ``name``.

        :param name:    Lower-case backend identifier the HOCON ``backend``
                        field will match against.
        :param builder: Callable that turns a resolved ``MemoryStoreConfig``
                        into a concrete ``MemoryStore`` instance.
        """
        cls._REGISTRY[name.strip().lower()] = builder

    @classmethod
    def valid_backends(cls) -> frozenset[str]:
        """Snapshot of registered backend names (handy for error messages / help)."""
        return frozenset(cls._REGISTRY)

    @classmethod
    def resolve_config(cls, tool_config_store: Optional[dict[str, Any]] = None) -> MemoryStoreConfig:
        """Build a ``MemoryStoreConfig`` by layering env overrides on top of HOCON.

        See :py:meth:`MemoryStoreConfig.resolve` for the precedence rules.

        :param tool_config_store: ``store_config`` dict from HOCON. ``None`` or
                                  ``{}`` yields a config populated purely from env.
        :return: A populated config.
        """
        return MemoryStoreConfig.resolve(tool_config_store)

    @classmethod
    def create(cls, tool_config_store: Optional[dict[str, Any]] = None) -> MemoryStore:
        """Build and return the backend selected by the resolved config.

        :param tool_config_store: ``store_config`` dict from HOCON.
        :return: A ready-to-use ``MemoryStore`` subclass instance.
        :raises ValueError: If the backend name is not in the registry.
        """
        config: MemoryStoreConfig = cls.resolve_config(tool_config_store)
        backend: str = (config.backend or "").strip().lower()

        builder: Optional[BackendBuilder] = cls._REGISTRY.get(backend)
        if builder is None:
            raise ValueError(f"Unknown memory backend '{config.backend}'. Valid options: {sorted(cls._REGISTRY)}.")

        logger.info(
            "Creating memory store backend: %s (root_path=%s)",
            backend,
            config.root_path,
        )
        return builder(config)


# Built-in backend registrations. Downstream code can add more via
# ``MemoryStoreFactory.register(...)`` without editing this file.
MemoryStoreFactory.register(
    MemoryStoreFactory.BACKEND_MARKDOWN_FILE,
    lambda config: MarkdownFileStore(root_path=config.root_path),
)
MemoryStoreFactory.register(
    MemoryStoreFactory.BACKEND_JSON_FILE,
    lambda config: JsonFileStore(root_path=config.root_path),
)
