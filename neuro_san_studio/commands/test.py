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

"""Implementation of the `ns test` command.

Wraps pytest with the project's environment variables applied so that both
coded-tool unit tests and fixture-based integration tests resolve the project's
networks without extra setup.

Two modes:

  Unit (default):
    pytest tests/ -m "not integration and not smoke"
    No API keys required.

  Integration (--integration):
    pytest -s -m "integration"
    Requires API keys and the project's agent server environment.

An optional positional ``path`` argument scopes the run to a specific test file
or directory, e.g. ``ns test tests/neuro_san_studio/coded_tools/my_tool/``.

Any extra arguments after ``--`` are forwarded verbatim to pytest, e.g.
``ns test -- -v -k test_my_case --tb=short``.
"""

import importlib.util
import os
import subprocess
import sys
from typing import List
from typing import Optional

from neuro_san_studio.commands.project_environment import ProjectEnvironment


class TestCommand:  # pylint: disable=too-few-public-methods
    """Run pytest for the current neuro-san-studio project.

    Applies the project's environment variables (``AGENT_MANIFEST_FILE``,
    ``AGENT_TOOL_PATH``, ``PYTHONPATH``, etc.) before launching pytest as a
    subprocess, so integration tests that load agent networks resolve the
    project's registries without any additional shell setup.
    """

    _UNIT_MARKER: str = "not integration and not smoke"
    _INTEGRATION_MARKER: str = "integration"
    _DEFAULT_TEST_PATH: str = "tests"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        path: Optional[str] = None,
        integration: bool = False,
        verbose: bool = False,
        extra_args: Optional[List[str]] = None,
        root_dir: Optional[str] = None,
    ):
        """Initialise the command.

        Args:
            path: Optional path to a test file or directory to scope the run.
                Defaults to ``tests/`` when not provided.
            integration: When ``True``, run integration tests (``-m integration``).
                Defaults to unit tests only.
            verbose: When ``True``, add ``--verbose`` to the pytest invocation.
            extra_args: Additional arguments forwarded verbatim to pytest
                (collected from the CLI via ``ctx.args``).
            root_dir: Project root directory. Defaults to the current working
                directory so the command works from any location.
        """
        self.path = path
        self.integration = integration
        self.verbose = verbose
        self.extra_args = extra_args or []
        self.root_dir = root_dir or os.getcwd()

    def _build_argv(self) -> List[str]:
        """Construct the pytest argv list.

        Returns:
            A list starting with ``[sys.executable, "-m", "pytest"]`` followed
            by marker, path, verbosity, and any caller-supplied extra args.
        """
        argv: List[str] = [sys.executable, "-m", "pytest"]

        if self.verbose:
            argv.append("--verbose")

        if self.integration:
            argv.extend(["-s", "-m", self._INTEGRATION_MARKER])
        else:
            argv.extend(["-m", self._UNIT_MARKER])

        argv.append(self.path if self.path else self._DEFAULT_TEST_PATH)

        argv.extend(self.extra_args)
        return argv

    def run(self) -> int:
        """Apply project env vars, launch pytest, and return its exit code.

        Returns:
            The pytest process exit code — ``0`` on success, non-zero on failure.
        """
        if importlib.util.find_spec("pytest") is None:
            print(
                "error: pytest is not installed. Install it with: pip install 'neuro-san-studio[dev]'", file=sys.stderr
            )
            return 1
        ProjectEnvironment(self.root_dir).apply()
        result: subprocess.CompletedProcess = subprocess.run(
            self._build_argv(),
            cwd=self.root_dir,
            check=False,
        )
        return result.returncode
