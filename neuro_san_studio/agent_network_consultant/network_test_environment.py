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

"""Scoped environment required by Neuro SAN's direct fixture driver."""

import logging
import os
import shutil
import tempfile
import threading
from types import TracebackType
from typing import ClassVar
from typing import Self

from neuro_san_studio.commands.project_environment import ProjectEnvironment

logger = logging.getLogger("network_consultant")


class NetworkTestEnvironment:
    """Provide direct-test configuration temporarily and restore the caller's environment."""

    MANAGED_VARIABLES: ClassVar[tuple[str, ...]] = (
        "AGENT_MANIFEST_FILE",
        "AGENT_TOOL_PATH",
        "AGENT_TOOLBOX_INFO_FILE",
        "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE",
        "AGENT_TEST_THINKING_BASIS",
    )
    ENVIRONMENT_LOCK: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, project_root: str | None = None) -> None:
        """
        Initialize a scoped direct-test environment.

        :param project_root: The project root containing registries and coded tools.
        """
        self._project_root = os.path.abspath(project_root or os.getcwd())
        self._original_values: dict[str, str | None] = {}
        self._thinking_directory: str | None = None

    def __enter__(self) -> Self:
        """
        Apply missing direct-test values for the duration of the scope.

        :return: This active environment scope.
        :raises OSError: If the temporary thinking directory cannot be created.
        :raises TypeError: If an environment value cannot be assigned.
        :raises ValueError: If an environment value is malformed.
        """
        NetworkTestEnvironment.ENVIRONMENT_LOCK.acquire()
        try:
            self._remember_environment()
            self._apply_project_defaults()
            self._apply_thinking_directory()
        except (OSError, TypeError, ValueError):
            self._restore_environment()
            self._cleanup_thinking_directory()
            NetworkTestEnvironment.ENVIRONMENT_LOCK.release()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Restore every caller-owned environment value and clean up temporary files.

        :param exc_type: The exception type leaving the scope, when present.
        :param exc_value: The exception leaving the scope, when present.
        :param traceback: The exception traceback leaving the scope, when present.
        """
        del exc_type, exc_value, traceback
        try:
            self._restore_environment()
            self._cleanup_thinking_directory()
        finally:
            NetworkTestEnvironment.ENVIRONMENT_LOCK.release()

    def _remember_environment(self) -> None:
        """Remember the caller's complete state for every managed variable."""
        for name in NetworkTestEnvironment.MANAGED_VARIABLES:
            self._original_values[name] = os.environ.get(name)

    def _apply_project_defaults(self) -> None:
        """Apply missing project paths using Studio's shared resolution rules."""
        project = ProjectEnvironment(self._project_root)
        tool_path = os.path.relpath(project.resolve_tool_path(), self._project_root)
        defaults: dict[str, str] = {
            "AGENT_MANIFEST_FILE": project.resolve_manifest_file(),
            "AGENT_TOOL_PATH": tool_path,
            "AGENT_TOOLBOX_INFO_FILE": project.resolve_toolbox_info_file(),
            "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE": project.resolve_designer_toolbox_info_file(),
        }
        for name, value in defaults.items():
            if name not in os.environ and value:
                os.environ[name] = value

    def _apply_thinking_directory(self) -> None:
        """Create and expose an isolated thinking directory only when the caller did not configure one."""
        if "AGENT_TEST_THINKING_BASIS" in os.environ:
            return
        self._thinking_directory = tempfile.mkdtemp(prefix="network_consultant_test_thinking_")
        os.environ["AGENT_TEST_THINKING_BASIS"] = self._thinking_directory

    def _restore_environment(self) -> None:
        """Restore managed variables to the exact state captured on entry."""
        for name, value in self._original_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _cleanup_thinking_directory(self) -> None:
        """Delete the owned thinking directory and report cleanup failures."""
        if self._thinking_directory is None:
            return
        try:
            shutil.rmtree(self._thinking_directory)
        except OSError as error:
            logger.warning(
                "Could not remove temporary Consultant thinking directory %s: %s",
                self._thinking_directory,
                error,
            )
        self._thinking_directory = None
