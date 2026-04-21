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
Filesystem-safe path component utilities shared by the store and tool layers.

Single source of truth for the "what counts as a safe path character" regex,
so :py:class:`MemoryStore` (which sanitises namespace components into file
paths) and :py:class:`PersistentMemoryTool` (which slugifies LLM-supplied
topic strings) cannot drift apart.
"""

from __future__ import annotations

import re


class PathComponent:
    """Sanitise / slugify strings into filesystem-safe identifiers.

    Two related operations over the same character set:

    * :py:meth:`sanitise` — case-preserving, always non-empty. Used by store
      backends that take already-structured namespace components and only
      need to guard against unexpected characters.
    * :py:meth:`slugify`  — case-folding, may return empty. Used by the tool
      layer to turn free-form LLM input (``"Mike Smith"``, ``"Project α"``)
      into a stable file name.
    """

    # Only characters safe on every mainstream filesystem. Anything else
    # collapses to ``_`` — prevents path-traversal or accidental directory
    # nesting if an unusual component sneaks through.
    _UNSAFE_PATTERN: re.Pattern = re.compile(r"[^A-Za-z0-9._-]+")

    @classmethod
    def sanitise(cls, part: str) -> str:
        """Replace unsafe characters with ``_``. Never returns an empty string.

        :param part: Raw path component.
        :return: Filesystem-safe string; falls back to ``"_"`` if ``part`` is
                 all-unsafe or empty.
        """
        return cls._UNSAFE_PATTERN.sub("_", str(part)) or "_"

    @classmethod
    def slugify(cls, name: str) -> str:
        """Lower-case, replace unsafe runs with ``_``, strip leading/trailing ``_``.

        May return an empty string when ``name`` is all-unsafe, so callers can
        detect "no usable slug" and fall back to a default.

        :param name: Raw free-form string (e.g. an LLM-supplied topic).
        :return: Lowercase filesystem-safe slug, possibly empty.
        """
        return cls._UNSAFE_PATTERN.sub("_", name.strip().lower()).strip("_")
