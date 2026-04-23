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
Factory that builds a concrete ``TopicStore`` from a HOCON ``store`` dict.
"""

from __future__ import annotations

import logging
from logging import Logger
from typing import Any
from typing import ClassVar
from typing import Optional

from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.markdown_file_store import MarkdownFileStore
from middleware.persistent_memory.topic_store import TopicStore


class TopicStoreFactory:  # pylint: disable=too-few-public-methods
    """
    Builds the right store from a HOCON ``store`` dict.
    """

    _DEFAULT_BACKEND: ClassVar[str] = "json_file"
    _DEFAULT_ROOT_PATH: ClassVar[str] = "./memory"
    _DEFAULT_MEMORY_FILE_NAME: ClassVar[str] = "memory"

    _logger: ClassVar[Logger] = logging.getLogger(f"{__name__}.TopicStoreFactory")

    @classmethod
    def create(cls, config: Optional[dict[str, Any]] = None) -> TopicStore:
        """
        Build the backend named by ``config['backend']``. Raises on unknown names.

        :param config: HOCON ``storage`` dict; recognised keys are ``backend``,
                       ``root_path``, and (json backend only) ``memory_file_name``.
        :return: A concrete ``TopicStore`` subclass instance.
        """
        cfg: dict[str, Any] = config or {}
        backend: str = str(cfg.get("backend") or cls._DEFAULT_BACKEND).strip().lower()
        root_path: str = cfg.get("root_path") or cls._DEFAULT_ROOT_PATH

        cls._logger.info("Creating memory store backend: %s (root_path=%s)", backend, root_path)

        if backend == "json_file":
            return JsonFileStore(
                root_path=root_path,
                memory_file_name=cfg.get("memory_file_name") or cls._DEFAULT_MEMORY_FILE_NAME,
            )
        if backend == "markdown_file":
            return MarkdownFileStore(root_path=root_path)
        raise ValueError(
            f"Unknown memory backend '{backend}'. Valid options: ['json_file', 'markdown_file']."
        )
