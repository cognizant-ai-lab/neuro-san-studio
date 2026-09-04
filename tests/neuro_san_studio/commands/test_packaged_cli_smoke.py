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

"""Smoke test for the fresh `pip install neuro-san-studio` flow.

Builds a wheel from this checkout, installs it into a clean virtual environment, and drives
the packaged `ns` console script through the sequence a brand-new user follows: `ns init`,
`ns import`, load every scaffolded network, check the project `.env`.

The rest of the test suite runs against the development checkout, where every registry and
template file is present whether or not the wheel ships it, and where `neuro_san_studio` is
importable whether or not the entry points are wired up. Bugs in exactly that gap reached
end users twice (a shared include missing from the scaffold, and the project `.env` not being
loaded by the CLI), so what is under test here is the installed artifact: the wheel's package
data, the console script, and the project the CLI writes into an empty directory.

Marked `smoke`: the wheel build plus a cold `pip install` of the full dependency tree takes
minutes, so `make test-unit` deselects it and a dedicated workflow runs it.
"""

import os
import re
import subprocess
import sys
import venv
from pathlib import Path
from typing import Dict
from typing import List
from typing import Set

import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# The networks `ns init` and `ns import` are asked for. `basic` and `agent_network_designer`
# between them pull in the aaosa includes, coded tools, MCP config and the generated-manifest
# include, which is the machinery a scaffold can be missing pieces of.
IMPORTED_NETWORKS: List[str] = ["basic", "agent_network_designer"]

# A manifest key declared with a bare `true` is served and public, so `ns chat --list` has to
# report it. Keys with a dict body are support networks marked `"public": false`; they are
# deliberately absent from that listing, so they can only be checked via the failure markers
# below.
PUBLIC_MANIFEST_KEY: re.Pattern = re.compile(r'^\s*"(?P<key>[^"]+)\.hocon"\s*:\s*true\s*,?\s*$', re.MULTILINE)

LISTED_AGENT: re.Pattern = re.compile(r'"agent_name"\s*:\s*"(?P<name>[^"]+)"')

# A registry file that fails to parse or validate is logged and skipped rather than raised, so
# loading "succeeds" with the network silently missing. Fail on the log lines instead.
LOAD_FAILURE_MARKERS: List[str] = [
    "Parse error in registry item",
    "Failed to restore registry item",
    # Prefix of both "manifest registry <file> has validation errors" and
    # "manifest registry <key> not found in <manifest>".
    "manifest registry",
]

# A syntactically valid key that no provider call is made with: tier 1 only checks that the
# variable is set to something other than a placeholder.
FAKE_OPENAI_KEY: str = "sk-not-a-real-key-only-checked-for-presence"

# Generous, because these bounds only exist to keep a hung subprocess from hanging all of CI:
# a cold `pip install` dominates the runtime and is the reason the install bound is separate.
INSTALL_TIMEOUT_SECONDS: int = 1800
COMMAND_TIMEOUT_SECONDS: int = 600


class PackagedProject:  # pylint: disable=too-few-public-methods
    """A project scaffolded by the `ns` console script of a freshly installed wheel."""

    def __init__(self, project_dir: Path, venv_dir: Path):
        """
        :param project_dir: The (empty) directory to scaffold the project into.
        :param venv_dir: The virtual environment the wheel is installed in.
        """
        self.project_dir: Path = project_dir
        bin_dir: Path = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        self.python: Path = bin_dir / ("python.exe" if os.name == "nt" else "python")
        self.ns: Path = bin_dir / ("ns.exe" if os.name == "nt" else "ns")
        self.env: Dict[str, str] = self._child_env(bin_dir)

    @staticmethod
    def _child_env(bin_dir: Path) -> Dict[str, str]:
        """
        Build the environment a fresh user's shell would have.

        The test process inherits whatever points at this checkout -- PYTHONPATH,
        AGENT_MANIFEST_FILE, AGENT_TOOL_PATH, an active venv -- and any of those would let the
        packaged CLI find files the wheel does not ship. Provider keys are dropped too, so the
        key the `.env` assertion looks for can only have come from the scaffolded project.

        :param bin_dir: The installed venv's script directory, put first on PATH.
        :return: The environment to run every `ns` invocation with.
        """
        dropped: Set[str] = {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "OPENAI_API_KEY"}
        env: Dict[str, str] = {
            key: value
            for key, value in os.environ.items()
            if key not in dropped and not key.startswith("AGENT_") and not key.startswith("NEURO_SAN_")
        }
        env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])
        return env

    def run(self, *args: str) -> subprocess.CompletedProcess:
        """
        Run the packaged `ns` console script in the project directory.

        :param args: Arguments to `ns`, e.g. ("import", "basic").
        :return: The completed process, with stdout and stderr merged so log lines written to
            either stream are covered by the failure-marker assertions.
        """
        return subprocess.run(
            [str(self.ns), *args],
            cwd=self.project_dir,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )


def _build_wheel(dist_dir: Path) -> Path:
    """
    Build a wheel from this checkout.

    :param dist_dir: Directory to write the wheel to.
    :return: Path to the built wheel.
    """
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=REPO_ROOT,
        check=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )
    wheels: List[Path] = sorted(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel in {dist_dir}, got {wheels}"
    return wheels[0]


@pytest.fixture(name="packaged_project", scope="module")
def fixture_packaged_project(tmp_path_factory: pytest.TempPathFactory) -> PackagedProject:
    """
    Install a wheel built from this checkout into a clean venv, then `ns init` and `ns import`.

    Module-scoped: the build and the install are the expensive part, and every assertion below
    reads the same scaffolded project without mutating it.

    :param tmp_path_factory: pytest's temporary-directory factory.
    :return: The scaffolded project, ready to run `ns` against.
    """
    root: Path = tmp_path_factory.mktemp("packaged")
    wheel: Path = _build_wheel(root / "dist")

    venv_dir: Path = root / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)

    project: PackagedProject = PackagedProject(project_dir=root / "project", venv_dir=venv_dir)
    project.project_dir.mkdir()
    subprocess.run(
        [str(project.python), "-m", "pip", "install", "--quiet", str(wheel)],
        check=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    init = project.run("init", "--providers", "openai")
    assert init.returncode == 0, f"`ns init` failed:\n{init.stdout}"

    imported = project.run("import", *IMPORTED_NETWORKS)
    assert imported.returncode == 0, f"`ns import` failed:\n{imported.stdout}"

    (project.project_dir / ".env").write_text(f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\n", encoding="utf-8")
    return project


def _expected_public_networks(project_dir: Path) -> Set[str]:
    """
    Read the networks the scaffolded manifest declares as public.

    :param project_dir: The scaffolded project root.
    :return: Agent network names, i.e. manifest keys without the .hocon suffix.
    """
    manifest: Path = project_dir / "registries" / "manifest.hocon"
    keys: Set[str] = {match.group("key") for match in PUBLIC_MANIFEST_KEY.finditer(manifest.read_text())}
    assert keys, f"no public networks found in {manifest}"
    return keys


def test_scaffolded_networks_load(packaged_project: PackagedProject) -> None:
    """Every network the scaffold and import wrote loads in the scaffolded project."""
    listed = packaged_project.run("chat", "--list")

    assert listed.returncode == 0, f"`ns chat --list` failed:\n{listed.stdout}"
    for marker in LOAD_FAILURE_MARKERS:
        assert marker not in listed.stdout, f"network failed to load:\n{listed.stdout}"

    served: Set[str] = {match.group("name") for match in LISTED_AGENT.finditer(listed.stdout)}
    missing: Set[str] = _expected_public_networks(packaged_project.project_dir) - served
    assert not missing, f"manifest networks missing from `ns chat --list`: {sorted(missing)}\n{listed.stdout}"


def test_check_llm_keys_reads_project_env(packaged_project: PackagedProject) -> None:
    """`ns check-llm-keys` reports a key that only the scaffolded project's .env sets."""
    checked = packaged_project.run("check-llm-keys", "--tier", "1")

    assert checked.returncode == 0, f"`ns check-llm-keys --tier 1` failed:\n{checked.stdout}"
    assert re.search(r"OPENAI_API_KEY:.*Set", checked.stdout), f"key not reported as set:\n{checked.stdout}"
