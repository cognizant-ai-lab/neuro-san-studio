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

"""List agent networks declared in the source neuro-san-studio root manifest."""

import logging
import os
from typing import Dict
from typing import List
from typing import Optional

from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer

from neuro_san_studio.utils.package_paths import PackagePaths

# pyhocon resolves `include "..."` directives relative to CWD; we chdir to the
# source dir while reading so they resolve. Demote any residual log noise.
logging.getLogger("pyhocon.config_parser").setLevel(logging.ERROR)


class AgentNetworkRegistry:  # pylint: disable=too-few-public-methods
    """List every agent network declared by the source root manifest, grouped by directory prefix."""

    def __init__(self, source_dir: Optional[str] = None):
        self.source_dir = source_dir or PackagePaths.installed_library_root()
        self.registries_dir = os.path.join(self.source_dir, "registries")

    def discover(self) -> Dict[str, List[str]]:
        """Return {group: [hocon_relative_path, ...]}.

        Groups are inferred from the path prefix of each key in the root manifest
        (e.g. ``basic/foo.hocon`` → group ``basic``). Keys without a prefix are
        bucketed under ``root``. No group list is hardcoded.
        """
        manifest_path = os.path.join(self.registries_dir, "manifest.hocon")
        if not os.path.exists(manifest_path):
            return {}

        # pyhocon's `include` directives are resolved relative to CWD, not the
        # manifest. chdir ensures `include "registries/<group>/manifest.hocon"`
        # paths in the root manifest resolve correctly.
        prev_cwd = os.getcwd()
        try:
            os.chdir(self.source_dir)
            raw = RawManifestRestorer().restore(file_reference=manifest_path)
        finally:
            os.chdir(prev_cwd)

        result: Dict[str, List[str]] = {}
        for key in raw:
            clean = key.strip('"')
            if not clean.endswith(".hocon"):
                continue
            group = clean.split("/", 1)[0] if "/" in clean else "root"
            result.setdefault(group, []).append(clean)

        return {g: sorted(paths) for g, paths in sorted(result.items())}
