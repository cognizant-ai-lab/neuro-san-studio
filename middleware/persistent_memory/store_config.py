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

"""Typed config carrier for :py:class:`TopicStoreFactory`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import ClassVar
from typing import Optional


@dataclass(frozen=True)
class StoreConfig:
    """
    Typed view of the HOCON ``memory_config.storage`` block.

    Carries backend-selection settings from the middleware to the factory
    without passing raw dicts around. Backend-specific fields (like
    ``memory_file_name``) are only honoured by the backends that use them.
    """

    DEFAULT_BACKEND: ClassVar[str] = "json_file"
    DEFAULT_ROOT_PATH: ClassVar[str] = "./memory"

    backend: str = DEFAULT_BACKEND
    root_path: str = DEFAULT_ROOT_PATH
    memory_file_name: Optional[str] = None

    @classmethod
    def from_dict(cls, cfg: Optional[dict[str, Any]]) -> "StoreConfig":
        """
        Build a ``StoreConfig`` from a raw HOCON ``storage`` dict. Missing keys fall back to defaults.

        :param cfg: Raw ``storage`` dict from HOCON; may be ``None``.
        :return: A ``StoreConfig`` populated from ``cfg``.
        """
        data: dict[str, Any] = cfg or {}
        return cls(
            backend=str(data.get("backend") or cls.DEFAULT_BACKEND).strip().lower(),
            root_path=str(data.get("root_path") or cls.DEFAULT_ROOT_PATH),
            memory_file_name=data.get("memory_file_name"),
        )
