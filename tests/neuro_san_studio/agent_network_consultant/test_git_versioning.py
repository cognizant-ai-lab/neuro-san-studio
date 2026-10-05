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

"""Tests for optional Consultant Git snapshot versioning."""

import subprocess
from unittest import TestCase
from unittest.mock import call
from unittest.mock import mock_open
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.git_versioning import GitVersioning


class TestGitVersioning(TestCase):
    """Verify Consultant snapshots use only an explicitly configured upstream destination."""

    def test_configured_remote_requires_an_explicit_destination(self) -> None:
        """Reject --git-versions before Git work begins when no upstream destination is configured."""
        environment = {GitVersioning.GIT_VERSIONS_REMOTE_ENV: ""}

        with (
            patch.dict("neuro_san_studio.agent_network_consultant.git_versioning.os.environ", environment),
            patch("neuro_san_studio.agent_network_consultant.git_versioning.tempfile.mkdtemp") as mkdtemp_mock,
            self.assertRaisesRegex(ValueError, GitVersioning.GIT_VERSIONS_REMOTE_ENV),
        ):
            GitVersioning.start_git_versioning("example", "run-id")

        mkdtemp_mock.assert_not_called()

    def test_start_uses_the_configured_destination_without_modifying_git_remotes(self) -> None:
        """Create the snapshot branch without adding or rewriting a remote in the user's repository."""
        created: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=["git"], returncode=0)
        with (
            patch.object(GitVersioning, "configured_remote", return_value="upstream"),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.tempfile.mkdtemp",
                return_value="worktree",
            ),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.subprocess.run",
                return_value=created,
            ) as run_mock,
            patch.object(GitVersioning, "write_git_branch") as write_branch_mock,
        ):
            result = GitVersioning.start_git_versioning("industry/example", "run-id")

        self.assertEqual("worktree", result)
        run_mock.assert_called_once_with(
            [
                "git",
                "worktree",
                "add",
                "-B",
                "consultant-versions/industry-example/run-id",
                "worktree",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        write_branch_mock.assert_called_once_with("consultant-versions/industry-example/run-id")

    def test_commit_pushes_the_snapshot_branch_to_the_configured_upstream(self) -> None:
        """Push directly to the configured destination without creating a persistent Git remote."""
        missing_version: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
            args=["git"], returncode=1, stdout=""
        )
        succeeded: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=["git"], returncode=0)
        branch: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="consultant-versions/example/run-id\n"
        )
        with (
            patch("builtins.open", mock_open(read_data="network content")),
            patch("neuro_san_studio.agent_network_consultant.git_versioning.os.makedirs"),
            patch.object(GitVersioning, "configured_remote", return_value="upstream"),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.subprocess.run",
                side_effect=[missing_version, succeeded, succeeded, branch, succeeded],
            ) as run_mock,
        ):
            GitVersioning.commit_hocon_version("worktree", "example.hocon", "Snapshot")

        self.assertEqual(
            call(
                [
                    "git",
                    "-C",
                    "worktree",
                    "push",
                    "upstream",
                    "HEAD:refs/heads/consultant-versions/example/run-id",
                ],
                check=True,
                capture_output=True,
                text=True,
            ),
            run_mock.call_args_list[-1],
        )
        for git_call in run_mock.call_args_list:
            self.assertNotIn("remote", git_call.args[0])

    def test_start_reports_temporary_directory_cleanup_failure(self) -> None:
        """Return no worktree while reporting failure to remove the unused temporary directory."""
        setup_error = subprocess.CalledProcessError(1, ["git"], stderr="setup failed")
        with (
            patch.object(GitVersioning, "configured_remote", return_value="upstream"),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.tempfile.mkdtemp", return_value="worktree"
            ),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.subprocess.run",
                side_effect=setup_error,
            ),
            patch("neuro_san_studio.agent_network_consultant.git_versioning.os.path.exists", return_value=True),
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.shutil.rmtree",
                side_effect=OSError("cleanup denied"),
            ),
            self.assertLogs("network_consultant", level="WARNING") as captured,
        ):
            result = GitVersioning.start_git_versioning("example", "run-id")

        self.assertIsNone(result)
        self.assertIn("cleanup denied", "\n".join(captured.output))

    def test_stop_reports_git_worktree_removal_failure(self) -> None:
        """Keep shutdown best-effort while reporting the complete Git removal failure."""
        removal_error = subprocess.CalledProcessError(1, ["git"], stderr="worktree is locked")
        with (
            patch(
                "neuro_san_studio.agent_network_consultant.git_versioning.subprocess.run", side_effect=removal_error
            ) as run_mock,
            self.assertLogs("network_consultant", level="WARNING") as captured,
        ):
            GitVersioning.stop_git_versioning("worktree")

        run_mock.assert_called_once_with(
            ["git", "worktree", "remove", "--force", "worktree"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("worktree is locked", "\n".join(captured.output))
