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

"""Tests for signal-driven Network Consultant cleanup."""

import os
import signal
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_cleanup import ConsultantCleanup
from neuro_san_studio.agent_network_consultant.git_versioning import GitVersioning


class TestConsultantCleanup(TestCase):
    """Verify Consultant signal cleanup removes its temporary Git worktree."""

    def test_sigterm_removes_git_worktree_before_exiting(self) -> None:
        """Remove the retained worktree before terminating with the SIGTERM status."""
        ConsultantCleanup.configure("worktree")

        with (
            patch.object(GitVersioning, "stop_git_versioning") as stop_git_versioning,
            patch.object(os, "_exit") as exit_process,
        ):
            ConsultantCleanup.handle_sigterm(signal.SIGTERM, None)

        stop_git_versioning.assert_called_once_with("worktree")
        exit_process.assert_called_once_with(128 + signal.SIGTERM)
