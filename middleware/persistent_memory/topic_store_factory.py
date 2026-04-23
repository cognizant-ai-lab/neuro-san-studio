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
Factory that builds a concrete ``TopicStore`` from a raw HOCON ``storage`` dict.
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
    Builds the right store from the raw HOCON ``storage`` dict.
    """

    DEFAULT_BACKEND: ClassVar[str] = "json_file"
    DEFAULT_FOLDER_NAME: ClassVar[str] = "./memory"

    _logger: ClassVar[Logger] = logging.getLogger(f"{__name__}.TopicStoreFactory")

    @classmethod
    def create(cls, config: Optional[dict[str, Any]]) -> TopicStore:
        """
        Build the backend named by ``config["backend"]``. Raises on unknown names.

        :param config: Raw ``storage`` dict from HOCON; may be ``None``.
        :return: A concrete ``TopicStore`` subclass instance.
        """
        data: dict[str, Any] = config or {}
        backend: str = str(data.get("backend") or cls.DEFAULT_BACKEND).strip().lower()
        folder_name: str = str(data.get("folder_name") or cls.DEFAULT_FOLDER_NAME)
        file_name: Optional[str] = data.get("file_name")

        cls._logger.info("Creating memory store backend: %s (folder_name=%s)", backend, folder_name)

        if backend == "json_file":
            # ``JsonFileStore`` applies the default and sanitises the stem itself;
            # an empty string here collapses to ``DEFAULT_FILE_NAME`` inside.
            return JsonFileStore(folder_name=folder_name, file_name=file_name or "")
        if backend == "markdown_file":
            return MarkdownFileStore(folder_name=folder_name)
        raise ValueError(f"Unknown memory backend '{backend}'. Valid options: ['json_file', 'markdown_file'].")
