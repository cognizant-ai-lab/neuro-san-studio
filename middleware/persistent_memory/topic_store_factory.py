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

import logging
from logging import Logger
from pathlib import Path
from typing import Any
from typing import ClassVar

from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.markdown_file_store import MarkdownFileStore
from middleware.persistent_memory.topic_store import TopicStore


class TopicStoreFactory:  # pylint: disable=too-few-public-methods
    """
    Builds the right store from the raw HOCON ``storage`` dict.
    """

    DEFAULT_BACKEND: ClassVar[str] = "json_file"
    DEFAULT_FOLDER_NAME: ClassVar[str] = "memory"

    # Anchor HOCON folder names to the repository root (the parent of the
    # ``middleware/`` package) so memory always lands inside the project
    # tree regardless of the process working directory.
    _REPO_ROOT: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent

    _logger: ClassVar[Logger] = logging.getLogger(f"{__name__}.TopicStoreFactory")

    @classmethod
    def _resolve_folder(cls, folder_name: str) -> str:
        """Anchor *folder_name* to the repository root.

        ``memory``, ``./memory``, and ``/memory`` all resolve to
        ``<repo_root>/memory``.  ``data/memory``, ``./data/memory``,
        and ``/data/memory`` all resolve to ``<repo_root>/data/memory``.

        Absolute paths that already exist on disk (e.g. a test tmpdir)
        are returned as-is so unit tests are not affected.

        :param folder_name: Raw value from HOCON or the default.
        :return: Absolute path string anchored to the repo root.
        """
        raw: Path = Path(folder_name).expanduser()
        if raw.is_absolute():
            if raw.exists():
                return str(raw.resolve())
            raw = Path(str(raw).lstrip("/"))
        return str((cls._REPO_ROOT / raw).resolve())

    @classmethod
    def create(
        cls,
        config: dict[str, Any] | None,
        sly_data: dict[str, Any] | None = None,
    ) -> TopicStore:
        """
        Build the backend named by ``config["backend"]``. Raises on unknown names.

        :param config:   Raw ``storage`` dict from HOCON; may be ``None``.
        :param sly_data: Per-request sly_data dict; forwarded to cloud backends
                         (e.g. ``Mem0Store``) that need per-user scoping.
        :return: A concrete ``TopicStore`` subclass instance.
        """
        data: dict[str, Any] = config or {}
        backend: str = str(data.get("backend") or cls.DEFAULT_BACKEND).strip().lower()
        folder_name: str = cls._resolve_folder(str(data.get("folder_name") or cls.DEFAULT_FOLDER_NAME))
        file_name: str | None = data.get("file_name")

        cls._logger.info("Creating memory store backend: %s (folder_name=%s)", backend, folder_name)

        if backend == "json_file":
            # ``JsonFileStore`` applies the default and sanitizes the stem itself;
            # an empty string here collapses to ``DEFAULT_FILE_NAME`` inside.
            return JsonFileStore(folder_name=folder_name, file_name=file_name or "")
        if backend == "markdown_file":
            return MarkdownFileStore(folder_name=folder_name)
        if backend == "mem0":
            try:
                from middleware.persistent_memory.mem0_store import Mem0Store  # pylint: disable=import-outside-toplevel  # noqa: I001
            except ImportError as exc:
                raise ImportError(
                    "The 'mem0' memory backend requires the optional 'mem0ai' dependency. "
                    'Install it with: pip install "mem0ai>=2.0.2,<3.0"'
                ) from exc

            return Mem0Store(sly_data=sly_data)
        raise ValueError(f"Unknown memory backend '{backend}'. Valid options: ['json_file', 'markdown_file', 'mem0'].")
