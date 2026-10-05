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

"""Child-process environment required by Neuro SAN's direct fixture driver."""

import logging
import os
import shutil
import tempfile

from neuro_san_studio.commands.project_environment import ProjectEnvironment

logger = logging.getLogger("network_consultant")


class NetworkTestEnvironment:
    """Build direct-test configuration for an isolated Consultant child process."""

    def __init__(self, project_root: str | None = None) -> None:
        """
        Initialize a direct-test environment builder for one child process.

        :param project_root: The project root containing registries and coded tools.
        """
        self._project_root = os.path.abspath(project_root or os.getcwd())
        self._thinking_directory: str | None = None

    def create(self) -> dict[str, str]:
        """
        Build a child environment without changing the current process.

        :return: A complete environment mapping for the Consultant child process.
        :raises OSError: If the temporary thinking directory cannot be created.
        """
        environment = dict(os.environ)
        project = ProjectEnvironment(self._project_root)
        defaults: dict[str, str] = {
            "AGENT_MANIFEST_FILE": project.resolve_manifest_file(),
            "AGENT_TOOL_PATH": project.resolve_tool_path(),
            "AGENT_TOOLBOX_INFO_FILE": project.resolve_toolbox_info_file(),
            "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE": project.resolve_designer_toolbox_info_file(),
        }
        for name, value in defaults.items():
            NetworkTestEnvironment._set_default(environment, name, value)
        self._add_project_to_python_path(environment)
        if environment.get("AGENT_TEST_THINKING_BASIS") is None:
            if self._thinking_directory is None:
                self._thinking_directory = tempfile.mkdtemp(prefix="network_consultant_test_thinking_")
            environment["AGENT_TEST_THINKING_BASIS"] = self._thinking_directory
        return environment

    def owned_thinking_directory(self) -> str | None:
        """
        Return the temporary thinking directory created for the child process.

        :return: The owned directory, or `None` when the caller supplied one.
        """
        return self._thinking_directory

    def _add_project_to_python_path(self, environment: dict[str, str]) -> None:
        """
        Ensure the child process can import project-local coded tools.

        :param environment: The child environment being assembled.
        """
        existing = environment.get("PYTHONPATH", "")
        for path in existing.split(os.pathsep):
            if path and os.path.abspath(path) == self._project_root:
                return
        environment["PYTHONPATH"] = existing + os.pathsep + self._project_root if existing else self._project_root

    @staticmethod
    def _set_default(environment: dict[str, str], name: str, value: str) -> None:
        """
        Add one default to the child environment without replacing a caller value.

        :param environment: The child environment being assembled.
        :param name: The environment variable name.
        :param value: The resolved default value.
        """
        if environment.get(name) is None and value:
            environment[name] = value

    @staticmethod
    def cleanup_owned_thinking_directory(thinking_directory: str | None) -> None:
        """
        Delete a child-process thinking directory and report cleanup failures.

        :param thinking_directory: The owned directory, or `None` for caller-owned storage.
        """
        if thinking_directory is None:
            return
        try:
            shutil.rmtree(thinking_directory)
        except OSError as error:
            logger.warning(
                "Could not remove temporary Consultant thinking directory %s: %s",
                thinking_directory,
                error,
            )
