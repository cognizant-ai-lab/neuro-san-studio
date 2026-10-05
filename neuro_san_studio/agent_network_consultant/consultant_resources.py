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
    """Manage in-memory fixture-ratio overrides and an optional Git worktree."""

    def __init__(self) -> None:
        """Initialize empty cleanup state."""
        self._success_ratio_overrides: dict[str, str] = {}
        self._git_worktree: str | None = None

    def success_ratio_overrides(self) -> dict[str, str]:
        """
        Return an isolated copy of fixture execution overrides.

        :return: Success ratios keyed by fixture basename.
        """
        return dict(self._success_ratio_overrides)

    def has_success_ratio_overrides(self) -> bool:
        """
        Return whether confidence handling selected stricter fixture ratios.

        :return: Whether any in-memory success-ratio overrides are active.
        """
        return bool(self._success_ratio_overrides)

    def remember_success_ratio_overrides(self, fixture_names: list[str], ratio: str) -> None:
        """
        Retain stricter ratios for subsequent executions of selected fixtures.

        :param fixture_names: Fixture basenames selected for stricter verification.
        :param ratio: The success ratio to use for those fixture executions.
        """
        for fixture_name in fixture_names:
            self._success_ratio_overrides[fixture_name] = ratio

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
