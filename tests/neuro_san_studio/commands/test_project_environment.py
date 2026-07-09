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

import pytest

from neuro_san_studio.commands.project_environment import ProjectEnvironment

_AGENT_VARS = ("AGENT_MANIFEST_FILE", "AGENT_TOOL_PATH", "MCP_SERVERS_INFO_FILE")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test from a clean slate for the env vars under test."""
    for var in (*_AGENT_VARS, "AGENT_TOOLBOX_INFO_FILE", "PYTHONPATH"):
        monkeypatch.delenv(var, raising=False)


def _project(tmp_path: Path) -> Path:
    """Lay out a minimal scaffolded project (manifest, coded_tools, mcp_info)."""
    (tmp_path / "registries").mkdir()
    (tmp_path / "registries" / "manifest.hocon").write_text("{}\n")
    (tmp_path / "coded_tools").mkdir()
    (tmp_path / "mcp").mkdir()
    (tmp_path / "mcp" / "mcp_info.hocon").write_text("{}\n")
    return tmp_path


class TestApply:
    """ProjectEnvironment.apply() sets the agent env vars from the project layout."""

    def test_sets_manifest_to_project_registries(self, tmp_path: Path) -> None:
        """AGENT_MANIFEST_FILE points at <root>/registries/manifest.hocon."""
        root = _project(tmp_path)
        ProjectEnvironment(str(root)).apply()
        assert os.environ["AGENT_MANIFEST_FILE"] == str(root / "registries" / "manifest.hocon")

    def test_sets_tool_path_to_project_coded_tools(self, tmp_path: Path) -> None:
        """AGENT_TOOL_PATH points at <root>/coded_tools."""
        root = _project(tmp_path)
        ProjectEnvironment(str(root)).apply()
        assert os.environ["AGENT_TOOL_PATH"] == str(root / "coded_tools")

    def test_sets_mcp_info_to_scaffolded_file(self, tmp_path: Path) -> None:
        """MCP_SERVERS_INFO_FILE points at the project's mcp/mcp_info.hocon when present."""
        root = _project(tmp_path)
        ProjectEnvironment(str(root)).apply()
        assert os.environ["MCP_SERVERS_INFO_FILE"] == str(root / "mcp" / "mcp_info.hocon")

    def test_adds_project_root_to_pythonpath(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The project root joins PYTHONPATH so neuro-san maps an absolute AGENT_TOOL_PATH to a module."""
        monkeypatch.delenv("PYTHONPATH", raising=False)
        root = _project(tmp_path)
        ProjectEnvironment(str(root)).apply()
        assert str(root) in os.environ["PYTHONPATH"].split(os.pathsep)


class TestRespectsExistingValues:
    """A user-provided env var is an override and must not be clobbered."""

    def test_keeps_existing_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An already-set AGENT_MANIFEST_FILE survives apply()."""
        root = _project(tmp_path)
        monkeypatch.setenv("AGENT_MANIFEST_FILE", "/custom/manifest.hocon")
        ProjectEnvironment(str(root)).apply()
        assert os.environ["AGENT_MANIFEST_FILE"] == "/custom/manifest.hocon"

    def test_keeps_existing_tool_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An already-set AGENT_TOOL_PATH survives apply()."""
        root = _project(tmp_path)
        monkeypatch.setenv("AGENT_TOOL_PATH", "/custom/tools")
        ProjectEnvironment(str(root)).apply()
        assert os.environ["AGENT_TOOL_PATH"] == "/custom/tools"


class TestResolveMcpInfoFile:
    """resolve_mcp_info_file precedence: env var, then scaffolded file, then bundled."""

    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicit MCP_SERVERS_INFO_FILE is used verbatim, ignoring the filesystem."""
        monkeypatch.setenv("MCP_SERVERS_INFO_FILE", "/custom/path/mcp_info.hocon")
        assert ProjectEnvironment(str(tmp_path)).resolve_mcp_info_file() == "/custom/path/mcp_info.hocon"

    def test_scaffolded_path_used_when_file_exists(self, tmp_path: Path) -> None:
        """With no env var, prefer <root>/mcp/mcp_info.hocon (what `init` scaffolds) over the bundled file."""
        root = _project(tmp_path)
        assert ProjectEnvironment(str(root)).resolve_mcp_info_file() == str(root / "mcp" / "mcp_info.hocon")

    def test_falls_back_to_bundled_when_no_env_and_no_scaffold(self, tmp_path: Path) -> None:
        """With no env var and no scaffolded file, fall back to the mcp_info.hocon shipped in the package."""
        result = ProjectEnvironment(str(tmp_path)).resolve_mcp_info_file()
        assert os.path.isfile(result)
        assert result.endswith(os.path.join("neuro_san_studio", "mcp", "mcp_info.hocon"))


class TestResolveToolboxInfoFile:
    """resolve_toolbox_info_file is a pure override: a path only when env-set or a file exists."""

    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicit AGENT_TOOLBOX_INFO_FILE is used verbatim, ignoring the filesystem."""
        monkeypatch.setenv("AGENT_TOOLBOX_INFO_FILE", "/custom/path/toolbox.hocon")
        assert ProjectEnvironment(str(tmp_path)).resolve_toolbox_info_file() == "/custom/path/toolbox.hocon"

    def test_default_path_used_when_file_exists(self, tmp_path: Path) -> None:
        """With no env var, fall back to <root>/neuro_san_studio/toolbox/toolbox_info.hocon if it exists."""
        toolbox = tmp_path / "neuro_san_studio" / "toolbox"
        toolbox.mkdir(parents=True)
        (toolbox / "toolbox_info.hocon").write_text("{}\n")
        assert ProjectEnvironment(str(tmp_path)).resolve_toolbox_info_file() == str(toolbox / "toolbox_info.hocon")

    def test_empty_when_no_env_and_no_file(self, tmp_path: Path) -> None:
        """With no env var and no file on disk, return "" so the env var stays unset."""
        assert ProjectEnvironment(str(tmp_path)).resolve_toolbox_info_file() == ""


class TestToolboxApply:
    """apply() exports the toolbox var only when resolution yields a real path."""

    def test_unset_when_no_toolbox_file(self, tmp_path: Path) -> None:
        """No toolbox file and no env var means AGENT_TOOLBOX_INFO_FILE stays unset."""
        root = _project(tmp_path)
        ProjectEnvironment(str(root)).apply()
        assert "AGENT_TOOLBOX_INFO_FILE" not in os.environ

    def test_set_when_toolbox_file_present(self, tmp_path: Path) -> None:
        """A scaffolded toolbox file is exported."""
        root = _project(tmp_path)
        toolbox = root / "neuro_san_studio" / "toolbox"
        toolbox.mkdir(parents=True)
        (toolbox / "toolbox_info.hocon").write_text("{}\n")
        ProjectEnvironment(str(root)).apply()
        assert os.environ["AGENT_TOOLBOX_INFO_FILE"] == str(toolbox / "toolbox_info.hocon")


class TestEnvFile:  # pylint: disable=too-few-public-methods
    """apply() loads a project-root .env so API keys are available."""

    def test_loads_dotenv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keys defined in <root>/.env are loaded into the environment."""
        root = _project(tmp_path)
        (root / ".env").write_text("NS_TEST_ENV_KEY=from_dotenv\n")
        monkeypatch.delenv("NS_TEST_ENV_KEY", raising=False)
        ProjectEnvironment(str(root)).apply()
        assert os.environ.get("NS_TEST_ENV_KEY") == "from_dotenv"
