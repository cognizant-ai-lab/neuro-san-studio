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

Nothing here imports from the checkout: the only requirements on the test process are
`pytest` and `build`, so a CI job can collect this file without installing the runtime
dependency tree it is about to install into the clean venv anyway.

Marked `smoke`: the wheel build plus a cold `pip install` of the full dependency tree takes
minutes, so `make test-unit` deselects it and a dedicated workflow runs it.
"""

import json
import os
import re
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Set

import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# What `ns init` installs into every new project. Its dependencies are `ns init`'s job to
# install and register, so they are covered by the served-network checks rather than listed.
DEFAULT_NETWORKS: List[str] = ["agent_network_designer"]

# One network on top of what `ns init` scaffolds, which is all it takes to exercise `ns import`.
IMPORTED_NETWORKS: List[str] = ["basic/hello_world"]

# `ns chat --list` prints log lines, then this anchor, then one JSON document.
LISTING_ANCHOR: str = "Available agents:"

# The validator's verdict line.
VALIDATION_PASSED: str = "Validation passed"

# A syntactically valid key that no provider call is made with: tier 1 only checks that the
# variable is set to something other than a placeholder.
FAKE_OPENAI_KEY: str = "sk-not-a-real-key-only-checked-for-presence"

# What a subprocess needs from the test process's environment to run at all: locate binaries,
# write temp files, talk to a package index through a proxy. Everything else -- PYTHONPATH,
# AGENT_*, NEURO_SAN_*, provider keys, MCP_SERVERS_INFO_FILE -- is dropped, so the packaged CLI
# can only find what the wheel ships and the key the `.env` assertion looks for can only have
# come from the scaffolded project.
INHERITED_VARIABLES: Set[str] = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    # Windows: the process cannot start, or Python cannot find its DLLs, without these.
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "USERPROFILE",
    "LOCALAPPDATA",
}
INHERITED_PREFIXES: tuple = ("PIP_", "SSL_CERT_", "REQUESTS_CA_", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")

# Generous, because these bounds only exist to keep a hung subprocess from hanging all of CI:
# a cold `pip install` dominates the runtime and is the reason the install bound is separate.
INSTALL_TIMEOUT_SECONDS: int = 1800
COMMAND_TIMEOUT_SECONDS: int = 600

# Lists the networks the scaffolded manifest serves, using the installed package's own reader
# so the test agrees with the CLI about which entries are live.
LIST_SERVED_SCRIPT: str = """
from neuro_san_studio.discovery.served_network_lister import ServedNetworkLister
lister = ServedNetworkLister(["registries/manifest.hocon"])
print("\\n".join(lister.list_names()))
for warning in lister.warnings:
    raise SystemExit(f"manifest warning: {warning}")
"""


def _clean_env() -> Dict[str, str]:
    """
    Build the environment a fresh user's shell would have.

    :return: An allow-listed copy of the test process's environment.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if key in INHERITED_VARIABLES or key.upper().startswith(INHERITED_PREFIXES)
    }


class PackagedProject:
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
        self.env: Dict[str, str] = _clean_env()
        self.env["PATH"] = os.pathsep.join([str(bin_dir), self.env.get("PATH", "")])

    def run(self, *args: str) -> subprocess.CompletedProcess:
        """
        Run the packaged `ns` console script in the project directory.

        :param args: Arguments to `ns`, e.g. ("import", "basic").
        :return: The completed process, with stdout and stderr merged so a failure report shows
            log lines written to either stream.
        """
        return self._run_in_venv([str(self.ns), *args])

    def served_networks(self) -> List[str]:
        """
        Ask the installed package which networks the scaffolded manifest serves.

        :return: Registry-relative network names, e.g. ``basic/hello_world``.
        """
        result = self._run_in_venv([str(self.python), "-c", LIST_SERVED_SCRIPT])
        assert result.returncode == 0, f"listing served networks failed:\n{result.stdout}"
        served: List[str] = [line.removeprefix("/") for line in result.stdout.splitlines() if line.strip()]
        assert served, f"no served networks in the scaffolded manifest:\n{result.stdout}"
        return served

    def _run_in_venv(self, command: List[str]) -> subprocess.CompletedProcess:
        """
        Run a command in the project directory with the clean environment.

        stdin is an empty pipe rather than a TTY, so a command that would prompt reads EOF
        instead of hanging the test.

        :param command: The command line to run.
        :return: The completed process, stdout and stderr merged.
        """
        return subprocess.run(
            command,
            cwd=self.project_dir,
            env=self.env,
            input="",
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
    env: Dict[str, str] = _clean_env()
    # The version comes from git metadata; CI checkouts are shallow, so it is pinned there.
    if "SETUPTOOLS_SCM_PRETEND_VERSION" in os.environ:
        env["SETUPTOOLS_SCM_PRETEND_VERSION"] = os.environ["SETUPTOOLS_SCM_PRETEND_VERSION"]
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(REPO_ROOT)],
        cwd=dist_dir,
        env=env,
        input="",
        text=True,
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
        env=project.env,
        input="",
        text=True,
        check=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    init = project.run("init", "--providers", "openai")
    assert init.returncode == 0, f"`ns init` failed:\n{init.stdout}"

    # `ns import` warns and exits 0 on a network it does not know, so the exit code alone
    # does not show the import happened.
    imported = project.run("import", *IMPORTED_NETWORKS)
    assert imported.returncode == 0, f"`ns import` failed:\n{imported.stdout}"
    manifest_text: str = (project.project_dir / "registries" / "manifest.hocon").read_text(encoding="utf-8")
    for network in IMPORTED_NETWORKS:
        assert (project.project_dir / "registries" / f"{network}.hocon").is_file(), (
            f"`ns import` did not copy {network}:\n{imported.stdout}"
        )
        assert f"{network}.hocon" in manifest_text, f"`ns import` did not register {network}:\n{imported.stdout}"

    (project.project_dir / ".env").write_text(f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\n", encoding="utf-8")
    return project


def test_scaffolded_networks_load(packaged_project: PackagedProject) -> None:
    """The networks the scaffold and the import wrote load and are listed in the scaffolded project.

    A registry file that fails to parse or validate is logged and skipped rather than raised,
    so the command exits 0 with the network silently missing. The listing itself is what is
    checked: it is the JSON document after the anchor, and every expected network must be in it.
    """
    listed = packaged_project.run("chat", "--list")
    assert listed.returncode == 0, f"`ns chat --list` failed:\n{listed.stdout}"

    _, anchor, listing = listed.stdout.partition(LISTING_ANCHOR)
    assert anchor, f"`ns chat --list` printed no listing:\n{listed.stdout}"
    payload: Dict[str, Any] = json.loads(listing)
    listed_agents: Set[str] = {agent.get("agent_name") for agent in payload.get("agents", [])}

    missing: Set[str] = set(DEFAULT_NETWORKS + IMPORTED_NETWORKS) - listed_agents
    assert not missing, f"networks missing from `ns chat --list`: {sorted(missing)}\n{listed.stdout}"


def test_served_networks_validate(packaged_project: PackagedProject) -> None:
    """Every served manifest entry passes `ns validate`.

    `ns chat --list` only reports public networks and tolerates a failed load by logging
    and skipping, so support networks (`"serve": true, "public": false`) could break without
    failing any assertion above. `ns validate` exits non-zero on a file that fails to parse,
    fails to validate, or is missing from the wheel, and it accepts `/agent_name` references
    to the other networks the manifest serves, so each served entry gets checked directly.

    The exit code alone is not enough: `ns` exits 0 on a usage error too, so the validator's
    own verdict has to be in the output.
    """
    for network in packaged_project.served_networks():
        result = packaged_project.run("validate", f"registries/{network}.hocon")
        assert result.returncode == 0, f"`ns validate` failed for {network}:\n{result.stdout}"
        assert VALIDATION_PASSED in result.stdout, f"`ns validate` gave no verdict for {network}:\n{result.stdout}"


def test_check_llm_keys_reads_project_env(packaged_project: PackagedProject) -> None:
    """`ns check-llm-keys` reports a key that only the scaffolded project's .env sets."""
    checked = packaged_project.run("check-llm-keys", "--tier", "1")

    assert checked.returncode == 0, f"`ns check-llm-keys --tier 1` failed:\n{checked.stdout}"
    assert re.search(r"(?m)^\s*OPENAI_API_KEY:.*Set", checked.stdout), f"key not reported as set:\n{checked.stdout}"
