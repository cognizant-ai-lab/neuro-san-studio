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

"""Normal and signal-driven cleanup for a Network Consultant run."""

import logging
import os
import signal
from typing import Any

from neuro_san_studio.agent_network_consultant.git_versioning import GitVersioning

logger = logging.getLogger("network_consultant")


class ConsultantCleanup:
    """Remember and remove an optional Git worktree during signal-driven cleanup."""

    # A signal handler cannot reach NetworkConsultantOrchestrator.execute()'s local run context.
    _git_worktree: str | None = None

    @staticmethod
    def configure(git_worktree: str | None = None) -> None:
        """
        Replace the resource removed by signal-driven cleanup.

        :param git_worktree: The optional Git worktree to remove.
        """
        ConsultantCleanup._git_worktree = git_worktree

    @staticmethod
    def remember_worktree(git_worktree: str | None) -> None:
        """
        Retain the optional Git worktree for signal-driven cleanup.

        :param git_worktree: The optional Git worktree to remove.
        """
        ConsultantCleanup._git_worktree = git_worktree

    @staticmethod
    def handle_sigterm(_signum: int, _frame: Any) -> None:
        """
        Remove the temporary Git worktree and terminate after an nsflow stop request.

        Python's default SIGTERM handling does not unwind `finally` blocks. Raising from this handler would unwind
        through `ThreadPoolExecutor.__exit__`, which waits for in-flight fixtures until nsflow escalates to SIGKILL.
        Direct cleanup followed by `os._exit` keeps worktree removal inside that shutdown window.

        :param _signum: The signal number supplied by the signal handler.
        :param _frame: The interrupted stack frame supplied by the signal handler.
        """
        logger.warning("Stop requested (SIGTERM) -- removing the temporary Git worktree before exit.")
        try:
            GitVersioning.stop_git_versioning(ConsultantCleanup._git_worktree)
        finally:
            os._exit(128 + signal.SIGTERM)
