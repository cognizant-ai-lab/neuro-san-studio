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

import os
from pathlib import Path

from dotenv import load_dotenv

from neuro_san_studio import mcp as _mcp_pkg
from neuro_san_studio import toolbox as _toolbox_pkg

# Path to the mcp_info.hocon that ships inside the neuro_san_studio package.
# Resolving via the imported package's __file__ works both in-repo (where
# neuro_san_studio/ is just a folder on sys.path) and after `pip install`
# (where it lives in site-packages), on every supported platform.
_BUNDLED_MCP_INFO_FILE = Path(_mcp_pkg.__file__).parent / "mcp_info.hocon"

# Same resolution for the two toolbox HOCONs the studio ships: the runtime toolbox that
# defines tools agent networks reference by name (`ddgs_search` and friends), and the
# curated palette agent_network_designer offers when designing a new network.
_BUNDLED_TOOLBOX_DIR = Path(_toolbox_pkg.__file__).parent
_BUNDLED_TOOLBOX_INFO_FILE = _BUNDLED_TOOLBOX_DIR / "toolbox_info.hocon"
_BUNDLED_DESIGNER_TOOLBOX_INFO_FILE = _BUNDLED_TOOLBOX_DIR / "agent_network_designer_toolbox_info.hocon"


class ProjectEnvironment:
    """Resolve and export the env vars neuro-san needs to serve a project's networks."""

    def __init__(self, root_dir: str):
        """Initialize for a project rooted at root_dir.

        Args:
            root_dir: The project root, typically the current working directory.
        """
        self.root_dir = Path(root_dir)

    def apply(self) -> None:
        """Export the agent env vars for this project (without clobbering overrides).

        This is the in-process entry point used by `ns chat`: after it runs, a direct
        neuro-san session in this process resolves the project's own networks. The
        project .env file is loaded once, globally, by the CLI's top-level callback
        before any subcommand runs.
        """
        self.set_pythonpath()
        self._setdefault_env("AGENT_MANIFEST_FILE", self.resolve_manifest_file())
        self._setdefault_env("AGENT_TOOL_PATH", self.resolve_tool_path())
        self._setdefault_env("MCP_SERVERS_INFO_FILE", self.resolve_mcp_info_file())
        toolbox_file = self.resolve_toolbox_info_file()
        if toolbox_file:
            self._setdefault_env("AGENT_TOOLBOX_INFO_FILE", toolbox_file)
        designer_toolbox_file = self.resolve_designer_toolbox_info_file()
        if designer_toolbox_file:
            self._setdefault_env("AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE", designer_toolbox_file)

    def resolve_manifest_file(self) -> str:
        """Resolve AGENT_MANIFEST_FILE: the env var if set, else <root>/registries/manifest.hocon."""
        return os.getenv("AGENT_MANIFEST_FILE") or str(self.root_dir / "registries" / "manifest.hocon")

    def resolve_tool_path(self) -> str:
        """Resolve AGENT_TOOL_PATH: the env var if set, else <root>/coded_tools."""
        return os.getenv("AGENT_TOOL_PATH") or str(self.root_dir / "coded_tools")

    def resolve_mcp_info_file(self) -> str:
        """Resolve the MCP servers info file path.

        Precedence:
          1. MCP_SERVERS_INFO_FILE env var (used verbatim if non-empty).
          2. <root>/mcp/mcp_info.hocon if it exists (what `init` scaffolds into a project).
          3. The mcp_info.hocon shipped inside the neuro_san_studio package.
        """
        env_value = os.getenv("MCP_SERVERS_INFO_FILE")
        if env_value:
            return env_value
        scaffolded_path = self.root_dir / "mcp" / "mcp_info.hocon"
        if scaffolded_path.is_file():
            return str(scaffolded_path)
        return str(_BUNDLED_MCP_INFO_FILE)

    def resolve_toolbox_info_file(self) -> str:
        """Resolve the toolbox info file path.

        Precedence mirrors resolve_mcp_info_file:
          1. AGENT_TOOLBOX_INFO_FILE env var (used verbatim; set it to "" to opt out and get
             only neuro-san's built-in toolbox).
          2. <root>/neuro_san_studio/toolbox/toolbox_info.hocon if it exists (an in-repo run,
             or a project that deliberately vendored its own).
          3. The toolbox_info.hocon shipped inside the neuro_san_studio package.

        Tier 3 matters because agent networks reference toolbox tools by name and neuro-san's
        built-in toolbox holds exactly one (`get_current_date_time`). Without it, a
        pip-installed project running agent_network_designer — which uses `ddgs_search` — dies
        with "Tool 'ddgs_search' is not defined", as does every network under registries/tools.
        The framework overlays whatever we return on top of its built-in set, so this is
        additive, never a replacement.
        """
        env_value = os.getenv("AGENT_TOOLBOX_INFO_FILE")
        if env_value is not None:
            return env_value
        project_path = self.root_dir / "neuro_san_studio" / "toolbox" / "toolbox_info.hocon"
        if project_path.is_file():
            return str(project_path)
        return str(_BUNDLED_TOOLBOX_INFO_FILE)

    def resolve_designer_toolbox_info_file(self) -> str:
        """Resolve the toolbox info file listing the tools agent_network_designer may pick from.

        Same three-tier precedence as resolve_toolbox_info_file, against
        AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE. This is a curated subset, not the runtime
        toolbox: coded_tools/agent_network_editor/get_toolbox.py reads it to tell the designer
        LLM which tools exist. It defaults to a path relative to the current directory, which
        only resolves for an in-repo run; exporting the resolved path here means a scaffolded
        project gets the real palette instead of an empty list and a recurring warning.
        """
        env_value = os.getenv("AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE")
        if env_value is not None:
            return env_value
        project_path = self.root_dir / "neuro_san_studio" / "toolbox" / "agent_network_designer_toolbox_info.hocon"
        if project_path.is_file():
            return str(project_path)
        return str(_BUNDLED_DESIGNER_TOOLBOX_INFO_FILE)

    def load_env_file(self) -> None:
        """Load a project-root .env file (if any) so API keys and other settings are available."""
        env_path = self.root_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded environment variables from: {env_path}")
        else:
            print(f"No .env file found at {env_path}. \nUsing defaults.\n")

    def set_pythonpath(self) -> None:
        """Add the project root to PYTHONPATH (idempotently) so coded_tools.* resolves.

        neuro-san reads PYTHONPATH at runtime to map an absolute AGENT_TOOL_PATH to a module
        path, so setting it here works for both `ns run`'s server subprocess and an in-process
        `ns chat`. A no-op when the root is already present.
        """
        existing: str = os.environ.get("PYTHONPATH", "")
        root = str(self.root_dir)
        normalized_root = self.root_dir.resolve()
        if any(Path(path).resolve() == normalized_root for path in existing.split(os.pathsep) if path):
            return
        os.environ["PYTHONPATH"] = existing + os.pathsep + root if existing else root

    @staticmethod
    def _setdefault_env(name: str, value: str) -> None:
        """Export value under name only if the user has not already set that env var."""
        if not os.environ.get(name):
            os.environ[name] = value
