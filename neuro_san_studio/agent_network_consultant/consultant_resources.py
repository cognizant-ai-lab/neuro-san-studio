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

"""Resources that require cleanup after a consultant run."""


class ConsultantResources:
    """Manage temporary fixture ratios and an optional Git worktree."""

    def __init__(self) -> None:
        """Initialize empty cleanup state."""
        self._original_ratios: dict[str, str] = {}
        self._git_worktree: str | None = None

    def original_ratios(self) -> dict[str, str]:
        """
        Return an isolated copy of changed fixture ratios.

        :return: The original fixture ratios.
        """
        return dict(self._original_ratios)

    def has_original_ratios(self) -> bool:
        """
        Return whether confidence handling changed any fixture ratios.

        :return: Whether original ratios must be restored.
        """
        return bool(self._original_ratios)

    def remember_original_ratios(self, ratios: dict[str, str]) -> None:
        """
        Retain fixture ratios that must be restored during cleanup.

        :param ratios: The original ratios keyed by fixture path.
        """
        self._original_ratios.update(ratios)

    def set_git_worktree(self, worktree: str | None) -> None:
        """
        Retain the optional Git worktree used by this run.

        :param worktree: The worktree path, or `None` when versioning is disabled.
        """
        self._git_worktree = worktree

    def git_worktree(self) -> str | None:
        """
        Return the optional Git worktree used by this run.

        :return: The worktree path, or `None` when versioning is disabled.
        """
        return self._git_worktree
