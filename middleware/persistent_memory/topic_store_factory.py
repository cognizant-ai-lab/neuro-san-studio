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
Factory that builds a concrete ``TopicStore`` from a :py:class:`StoreConfig`.
"""

from __future__ import annotations

import logging
from logging import Logger
from typing import ClassVar

from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.markdown_file_store import MarkdownFileStore
from middleware.persistent_memory.store_config import StoreConfig
from middleware.persistent_memory.topic_store import TopicStore


class TopicStoreFactory:  # pylint: disable=too-few-public-methods
    """
    Builds the right store from a :py:class:`StoreConfig`.
    """

    _logger: ClassVar[Logger] = logging.getLogger(f"{__name__}.TopicStoreFactory")

    @classmethod
    def create(cls, config: StoreConfig) -> TopicStore:
        """
        Build the backend named by ``config.backend``. Raises on unknown names.

        :param config: Typed store config (see :py:class:`StoreConfig`).
        :return: A concrete ``TopicStore`` subclass instance.
        """
        cls._logger.info("Creating memory store backend: %s (root_path=%s)", config.backend, config.root_path)

        if config.backend == "json_file":
            # ``JsonFileStore`` applies the default and sanitises the stem itself;
            # an empty string here collapses to ``DEFAULT_MEMORY_FILE_NAME`` inside.
            return JsonFileStore(
                root_path=config.root_path,
                memory_file_name=config.memory_file_name or "",
            )
        if config.backend == "markdown_file":
            return MarkdownFileStore(root_path=config.root_path)
        raise ValueError(f"Unknown memory backend '{config.backend}'. Valid options: ['json_file', 'markdown_file'].")
