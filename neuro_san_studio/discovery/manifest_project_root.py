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

"""Derive the project root implied by an agent network manifest path."""

import os
from typing import Optional


class ManifestProjectRoot:  # pylint: disable=too-few-public-methods
    """Derive the project root implied by a manifest path.

    In the standard layout the manifest lives in ``<root>/registries/``, and the ``include
    "registries/..."`` directives inside it are written relative to ``<root>``. That root is also what
    ``HoconValidatorCli`` derives as its default registry directory from a single ``AGENT_MANIFEST_FILE``.
    A manifest that does not sit in a ``registries`` directory implies no root at all, and callers fall
    back to the current working directory, as the library does.
    """

    REGISTRIES_DIR_NAME: str = "registries"

    def __init__(self, manifest_file: str):
        """Initialize with the manifest path. A relative path is resolved against the current working directory."""
        self.manifest_file = manifest_file

    def resolve(self) -> Optional[str]:
        """Return the absolute project root, or ``None`` when the manifest is not inside a ``registries`` folder."""
        registries_dir: str = os.path.dirname(os.path.abspath(self.manifest_file))
        if os.path.basename(registries_dir) != self.REGISTRIES_DIR_NAME:
            return None
        return os.path.dirname(registries_dir)
