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

"""Optional isolated git snapshots for Network Consultant runs."""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles

logger = logging.getLogger("network_consultant")


class GitVersioning:
    """Create and publish isolated per-run HOCON snapshots."""

    @staticmethod
    def write_git_branch(branch: str) -> None:
        """
        Persist which branch --git-versions is committing this run's snapshots to, so nsflow's UI can surface it
        (mirrors write_tool_issues) -- a no-op when not running as an nsflow job.

        :param branch: The Git branch name to publish.
        """
        ConsultantJobFiles.write("git_branch.txt", branch)

    # --git-versions commits land here: <prefix>/<network>/<run-id>, never on whatever branch the
    # person running this already has checked out.
    GIT_VERSIONS_BRANCH_PREFIX = "consultant-versions"

    GIT_VERSIONS_REMOTE_ENV = "NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE"

    @staticmethod
    def _remove_temporary_directory(directory: str) -> None:
        """
        Remove an unused temporary worktree directory while reporting failures.

        :param directory: The temporary directory to remove.
        """
        if not os.path.exists(directory):
            return
        try:
            shutil.rmtree(directory)
        except OSError as error:
            logger.warning("Could not remove temporary Git worktree directory %s: %s", directory, error)

    @staticmethod
    def configured_remote() -> str:
        """
        Return the explicitly configured destination for Consultant snapshot branches.

        :return: The configured Git remote name or repository URL.
        :raises ValueError: If no Git versions destination is configured.
        """
        remote = os.environ.get(GitVersioning.GIT_VERSIONS_REMOTE_ENV, "").strip()
        if remote:
            return remote
        raise ValueError(
            "--git-versions requires NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE to name the upstream Git remote "
            "or repository URL."
        )

    @staticmethod
    def start_git_versioning(network_name: str, run_id: str) -> Optional[str]:
        """
        Set up an isolated git worktree checked out to a dedicated consultant-versions/<network>/<run-id> branch,
        for committing/pushing a snapshot of the network's hocon file at each meaningful checkpoint -- without ever
        touching whatever branch or uncommitted changes the person running this already has checked out (no `git
        checkout` against the real working tree, ever). Returns the worktree's path, or None (after logging a
        warning) if this isn't inside a usable git repo -- versioning is then skipped for the rest of this run
        rather than failing it outright over a nice-to-have.

        :param network_name: The target network name.
        :param run_id: The unique Consultant run identifier.
        :return: The resulting value.
        :raises ValueError: If the upstream Git destination is not configured.
        """
        remote = GitVersioning.configured_remote()
        branch = f"{GIT_VERSIONS_BRANCH_PREFIX}/{network_name.replace('/', '-')}/{run_id}"
        worktree_dir = tempfile.mkdtemp(prefix="network_consultant_git_")
        try:
            subprocess.run(
                ["git", "worktree", "add", "-B", branch, worktree_dir, "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr
            logger.warning("--git-versions requested but could not set up a git worktree (%s); skipping.", detail)
            GitVersioning._remove_temporary_directory(worktree_dir)
            return None
        except FileNotFoundError as exc:
            detail = str(exc)
            logger.warning("--git-versions requested but could not set up a git worktree (%s); skipping.", detail)
            GitVersioning._remove_temporary_directory(worktree_dir)
            return None
        logger.info(
            "Versioning network hocon snapshots to branch %r on configured upstream %r.",
            branch,
            remote,
        )
        GitVersioning.write_git_branch(branch)
        return worktree_dir

    @staticmethod
    def commit_hocon_version(worktree_dir: Optional[str], hocon_file: str, message: str) -> None:
        """
        Copy the network's current hocon content into the versioning worktree, commit it there if it differs from
        the branch's last commit, and push. A no-op if versioning was never started (worktree setup failed, or
        --git-versions wasn't passed). The "did it change" check compares content directly against the branch's own
        last commit (`git show HEAD:...`) rather than `git diff --cached --quiet` -- the latter trusts the working
        tree's file-stat cache to skip re-hashing, which can misjudge a file rewritten within the same on-disk
        mtime tick as its last stage (this loop's own checkpoints can land less than a second apart). Push/commit
        failures are logged and swallowed -- a rejected push or a network blip shouldn't take down the fix loop
        over this. The push targets the configured remote name or URL directly and never adds or rewrites a remote
        in the user's repository.

        :param worktree_dir: The optional Git worktree directory.
        :param hocon_file: The registries-relative HOCON file name.
        :param message: The message sent to the Consultant or stored in a verdict.
        :raises ValueError: If the upstream Git destination is no longer configured.
        """
        if worktree_dir is None:
            return
        relative_path = os.path.join("registries", hocon_file)
        with open(relative_path, encoding="utf-8") as source_file:
            new_content = source_file.read()
        last_committed = subprocess.run(
            ["git", "-C", worktree_dir, "show", f"HEAD:{relative_path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if last_committed.returncode == 0 and last_committed.stdout == new_content:
            return  # Identical to the branch's last commit -- nothing new to save.
        dest_path = os.path.join(worktree_dir, relative_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as dest_file:
            dest_file.write(new_content)
        try:
            remote = GitVersioning.configured_remote()
            subprocess.run(
                ["git", "-C", worktree_dir, "add", relative_path], check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-m", message], check=True, capture_output=True, text=True
            )
            branch_result = subprocess.run(
                ["git", "-C", worktree_dir, "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
            )
            branch = branch_result.stdout.strip()
            if not branch:
                logger.warning("Could not push a version snapshot because the temporary worktree has no branch.")
                return
            subprocess.run(
                ["git", "-C", worktree_dir, "push", remote, f"HEAD:refs/heads/{branch}"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Committed and pushed a version snapshot: %s", message)
        except subprocess.CalledProcessError as exc:
            logger.warning("Could not commit/push a version snapshot (%s); continuing without it.", exc.stderr or exc)

    @staticmethod
    def stop_git_versioning(worktree_dir: Optional[str]) -> None:
        """
        Remove the versioning worktree created by _start_git_versioning, if any. The branch itself (and everything
        committed to it) is left alone -- only the temporary checkout goes away.

        :param worktree_dir: The optional Git worktree directory.
        """
        if worktree_dir is None:
            return
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_dir],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            logger.warning("Could not remove Git worktree %s: %s", worktree_dir, error.stderr or error)
        except FileNotFoundError as error:
            logger.warning("Could not remove Git worktree %s: %s", worktree_dir, error)


GIT_VERSIONS_BRANCH_PREFIX = GitVersioning.GIT_VERSIONS_BRANCH_PREFIX
