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

from neuro_san_studio.agent_network_consultant.fixture_ratio_manager import FixtureRatioManager
from neuro_san_studio.agent_network_consultant.git_versioning import GitVersioning

logger = logging.getLogger("network_consultant")


class ConsultantCleanup:
    """Remember and restore temporary fixture ratios and an optional Git worktree."""

    # A signal handler cannot reach NetworkConsultantOrchestrator.execute()'s local run context.
    _state: dict[str, Any] = {"original_ratios": {}, "git_worktree": None}

    @staticmethod
    def configure(original_ratios: dict[str, str], git_worktree: str | None = None) -> None:
        """
        Replace the resources restored by normal or signal-driven cleanup.

        :param original_ratios: The original fixture ratios known at configuration time.
        :param git_worktree: The optional Git worktree to remove.
        """
        ConsultantCleanup._state = {
            "original_ratios": dict(original_ratios),
            "git_worktree": git_worktree,
        }

    @staticmethod
    def remember_ratios(original_ratios: dict[str, str]) -> None:
        """
        Add newly changed fixture ratios to signal-driven cleanup state.

        :param original_ratios: The additional original ratios keyed by fixture path.
        """
        cleanup_ratios = ConsultantCleanup._state.get("original_ratios", {})
        cleanup_ratios.update(original_ratios)

    @staticmethod
    def remember_worktree(git_worktree: str | None) -> None:
        """
        Retain the optional Git worktree for signal-driven cleanup.

        :param git_worktree: The optional Git worktree to remove.
        """
        ConsultantCleanup._state.update({"git_worktree": git_worktree})

    @staticmethod
    def handle_sigterm(_signum: int, _frame: Any) -> None:
        """
        Restore on-disk state immediately and terminate after an nsflow stop request.

        Python's default SIGTERM handling does not unwind `finally` blocks. Raising from this handler would unwind
        through `ThreadPoolExecutor.__exit__`, which waits for in-flight fixtures until nsflow escalates to SIGKILL.
        Direct restoration followed by `os._exit` keeps cleanup inside that shutdown window.

        :param _signum: The signal number supplied by the signal handler.
        :param _frame: The interrupted stack frame supplied by the signal handler.
        """
        logger.warning("Stop requested (SIGTERM) -- restoring fixture success ratios before exit.")
        try:
            FixtureRatioManager.restore(ConsultantCleanup._state.get("original_ratios", {}))
            GitVersioning.stop_git_versioning(ConsultantCleanup._state.get("git_worktree"))
        finally:
            os._exit(128 + signal.SIGTERM)
