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
`ns import`, load every scaffolded network, validate every served one, check the project `.env`.

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
from typing import Tuple

import pytest
from pyhocon import ConfigFactory

pytestmark = pytest.mark.smoke

REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# One network on top of what `ns init` scaffolds, which is all it takes to exercise `ns import`
# and the dependency walk behind it. internet_info_gatherer is the one the default scaffold needs
# and does not install: agent_network_designer calls /tools/internet_info_gatherer, so without it
# the designer registry fails validation and neuro-san drops it.
IMPORTED_NETWORKS: List[str] = ["tools/internet_info_gatherer"]

LISTED_AGENT: re.Pattern = re.compile(r'"agent_name"\s*:\s*"(?P<name>[^"]+)"')

# A registry file that fails to parse or validate is logged and skipped rather than raised, so
# loading "succeeds" with the network silently missing and the command still exits 0. Matching
# neuro-san's exact log wording would go stale the first time those messages are reworded, so
# any of these words in a log line counts as a failed load; a clean run has none of them.
LOAD_FAILURE_WORDS: re.Pattern = re.compile(
    r"\b(error|errors|fail|fails|failed|failure|failures|skip|skipped|skipping|traceback)\b",
    re.IGNORECASE,
)

# Tells the log lines apart from the JSON listing they surround: agent descriptions are prose
# and say things like "in case its first configured LLM fails", which is not a failure.
JSON_FIELD: re.Pattern = re.compile(r'^\s*"[^"]+"\s*:')

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
    # Run the build from outside the checkout: ``python -m build`` puts the cwd on
    # sys.path, and a leftover ``build/`` dir at the repo root (gitignored output of
    # ``python setup.py build``) would shadow the ``build`` package itself.
    dist_dir.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(REPO_ROOT)],
        cwd=dist_dir,
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


def _scaffold_manifest_entries(project_dir: Path) -> Tuple[Set[str], Set[str]]:
    """
    Read the networks the scaffolded manifest serves and the subset it lists as public.

    A manifest key declared with a bare `true` is served and public. Keys with a dict body
    are support networks declared with explicit `serve`/`public` flags. Includes are
    resolved relative to the project root, matching how the packaged CLI sees them.

    :param project_dir: The scaffolded project root.
    :return: (served keys, public keys). Keys are the manifest's registry-relative
        ``.hocon`` file names, e.g. ``basic/hello_world.hocon``.
    """
    manifest: Path = project_dir / "registries" / "manifest.hocon"
    parsed = ConfigFactory.parse_string(manifest.read_text(encoding="utf-8"), basedir=str(project_dir))

    # pyhocon keeps the literal quotes of a quoted key, so strip them back off.
    entries = ((key.strip().strip('"'), value) for key, value in parsed.items())
    served: Set[str] = set()
    public: Set[str] = set()
    for key, value in entries:
        if value is True:
            served.add(key)
            public.add(key)
        elif isinstance(value, dict):
            if value.get("serve", False):
                served.add(key)
            if value.get("public", False):
                public.add(key)

    assert served, f"no served networks found in {manifest}"
    return served, public


def test_scaffolded_networks_load(packaged_project: PackagedProject) -> None:
    """Every network the scaffold and import wrote loads in the scaffolded project."""
    listed = packaged_project.run("chat", "--list")

    assert listed.returncode == 0, f"`ns chat --list` failed:\n{listed.stdout}"
    complaints: List[str] = [
        line for line in listed.stdout.splitlines() if not JSON_FIELD.match(line) and LOAD_FAILURE_WORDS.search(line)
    ]
    assert not complaints, "`ns chat --list` reported a problem:\n" + "\n".join(complaints)

    listed_agents: Set[str] = {match.group("name") for match in LISTED_AGENT.finditer(listed.stdout)}
    _, public = _scaffold_manifest_entries(packaged_project.project_dir)
    missing: Set[str] = {key.removesuffix(".hocon") for key in public} - listed_agents
    assert not missing, f"manifest networks missing from `ns chat --list`: {sorted(missing)}\n{listed.stdout}"


def test_served_networks_validate(packaged_project: PackagedProject) -> None:
    """Every served manifest entry passes `ns validate`.

    `ns chat --list` only reports public networks and tolerates a failed load by logging
    and skipping, so support networks (`"serve": true, "public": false`) could break without
    failing any assertion above. `ns validate` exits non-zero on a file that fails to parse,
    fails to validate, or is missing from the wheel, so each served entry gets checked
    directly instead of relying on the absence of a log marker.
    """
    served, _ = _scaffold_manifest_entries(packaged_project.project_dir)

    # `ns validate` checks one file at a time, so `/agent_name` references to the other
    # networks in the manifest must be declared to it explicitly. At load time they
    # resolve as external agents, which is exactly what `--external-agents` declares.
    external_agents: str = ",".join(f"/{key.removesuffix('.hocon')}" for key in sorted(served))
    for network_file in sorted(served):
        result = packaged_project.run("validate", f"registries/{network_file}", "--external-agents", external_agents)
        assert result.returncode == 0, f"`ns validate` failed for {network_file}:\n{result.stdout}"


def test_check_llm_keys_reads_project_env(packaged_project: PackagedProject) -> None:
    """`ns check-llm-keys` reports a key that only the scaffolded project's .env sets."""
    checked = packaged_project.run("check-llm-keys", "--tier", "1")

    assert checked.returncode == 0, f"`ns check-llm-keys --tier 1` failed:\n{checked.stdout}"
    assert re.search(r"OPENAI_API_KEY:.*Set", checked.stdout), f"key not reported as set:\n{checked.stdout}"
