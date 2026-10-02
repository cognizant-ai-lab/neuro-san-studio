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

from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_DIR
from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_ID

logger = logging.getLogger("network_consultant")


class GitVersioning:
    """Create and publish isolated per-run HOCON snapshots."""

    @staticmethod
    def write_git_branch(branch: str) -> None:
        """Persist which branch --git-versions is committing this run's snapshots to, so nsflow's UI
        can surface it (mirrors write_tool_issues) -- a no-op when not running as an nsflow job."""
        if not (NSFLOW_JOB_ID and NSFLOW_JOB_DIR):
            return
        branch_path = os.path.join(NSFLOW_JOB_DIR, f"{NSFLOW_JOB_ID}.git_branch.txt")
        with open(branch_path, "w", encoding="utf-8") as branch_file:
            branch_file.write(branch)

    # --git-versions commits land here: <prefix>/<network>/<run-id>, never on whatever branch the
    # person running this already has checked out.
    GIT_VERSIONS_BRANCH_PREFIX = "consultant-versions"

    # Pushed to a dedicated remote rather than `origin` -- these are throwaway per-run snapshots,
    # not something to land on whatever repo `origin` happens to point at (e.g. a shared upstream
    # project). Override via env var for a different personal remote.
    GIT_VERSIONS_REMOTE_NAME = "network-consultant-versions"
    GIT_VERSIONS_REMOTE_URL: str = os.environ.get(
        "NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE", "https://github.com/shrushtiimehta/consultant.git"
    )

    @staticmethod
    def ensure_git_versions_remote() -> None:
        """Add GIT_VERSIONS_REMOTE_NAME pointing at GIT_VERSIONS_REMOTE_URL if it isn't already
        configured, or repoint it if some other URL is there under that name -- so a change to
        NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE takes effect without manual `git remote` surgery."""
        existing = subprocess.run(
            ["git", "remote", "get-url", GIT_VERSIONS_REMOTE_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        if existing.returncode == 0:
            if existing.stdout.strip() != GIT_VERSIONS_REMOTE_URL:
                subprocess.run(
                    ["git", "remote", "set-url", GIT_VERSIONS_REMOTE_NAME, GIT_VERSIONS_REMOTE_URL], check=True
                )
            return
        subprocess.run(["git", "remote", "add", GIT_VERSIONS_REMOTE_NAME, GIT_VERSIONS_REMOTE_URL], check=True)

    @staticmethod
    def start_git_versioning(network_name: str, run_id: str) -> Optional[str]:
        """Set up an isolated git worktree checked out to a dedicated
        consultant-versions/<network>/<run-id> branch, for committing/pushing a snapshot of the
        network's hocon file at each meaningful checkpoint -- without ever touching whatever branch
        or uncommitted changes the person running this already has checked out (no `git checkout`
        against the real working tree, ever). Returns the worktree's path, or None (after logging a
        warning) if this isn't inside a usable git repo -- versioning is then skipped for the rest of
        this run rather than failing it outright over a nice-to-have.
        """
        branch = f"{GIT_VERSIONS_BRANCH_PREFIX}/{network_name.replace('/', '-')}/{run_id}"
        worktree_dir = tempfile.mkdtemp(prefix="network_consultant_git_")
        try:
            GitVersioning.ensure_git_versions_remote()
            subprocess.run(
                ["git", "worktree", "add", "-B", branch, worktree_dir, "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            logger.warning("--git-versions requested but could not set up a git worktree (%s); skipping.", detail)
            shutil.rmtree(worktree_dir, ignore_errors=True)
            return None
        logger.info(
            "Versioning network hocon snapshots to branch %r on remote %r (%s).",
            branch,
            GIT_VERSIONS_REMOTE_NAME,
            GIT_VERSIONS_REMOTE_URL,
        )
        GitVersioning.write_git_branch(branch)
        return worktree_dir

    @staticmethod
    def commit_hocon_version(worktree_dir: Optional[str], hocon_file: str, message: str) -> None:
        """Copy the network's current hocon content into the versioning worktree, commit it there if
        it differs from the branch's last commit, and push. A no-op if versioning was never started
        (worktree setup failed, or --git-versions wasn't passed). The "did it change" check compares
        content directly against the branch's own last commit (`git show HEAD:...`) rather than
        `git diff --cached --quiet` -- the latter trusts the working tree's file-stat cache to skip
        re-hashing, which can misjudge a file rewritten within the same on-disk mtime tick as its
        last stage (this loop's own checkpoints can land less than a second apart). Push/commit
        failures are logged and swallowed -- a rejected push or a network blip shouldn't take down
        the fix loop over this."""
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
            subprocess.run(
                ["git", "-C", worktree_dir, "add", relative_path], check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-m", message], check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "push", "-u", GIT_VERSIONS_REMOTE_NAME, "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Committed and pushed a version snapshot: %s", message)
        except subprocess.CalledProcessError as exc:
            logger.warning("Could not commit/push a version snapshot (%s); continuing without it.", exc.stderr or exc)

    @staticmethod
    def stop_git_versioning(worktree_dir: Optional[str]) -> None:
        """Remove the versioning worktree created by _start_git_versioning, if any. The branch itself
        (and everything committed to it) is left alone -- only the temporary checkout goes away."""
        if worktree_dir is None:
            return
        subprocess.run(["git", "worktree", "remove", "--force", worktree_dir], capture_output=True, check=False)


GIT_VERSIONS_BRANCH_PREFIX = GitVersioning.GIT_VERSIONS_BRANCH_PREFIX
GIT_VERSIONS_REMOTE_NAME = GitVersioning.GIT_VERSIONS_REMOTE_NAME
GIT_VERSIONS_REMOTE_URL = GitVersioning.GIT_VERSIONS_REMOTE_URL
