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

"""Shared status-line helpers for ``ns`` CLI commands.

The init/import/export commands all surface step-by-step progress with the same prefixed
style — ``[ok]``, ``[skip]``, ``[warn]``, ``[err]``, ``[info]``. Centralizing the helpers
keeps the column alignment and Rich color scheme consistent across commands; emoji are
intentionally avoided so the output renders the same in CI logs, plain terminals, and
copy-pasted tickets.

Rich treats bare ``[xxx]`` as markup, so the leading bracket is escaped with a backslash
in each format string.
"""

from rich.console import Console


class CliStatus:
    """Shared status-line printers for ``ns`` CLI commands."""

    # Class-level Console — Rich is happy to share one across writers, and the
    # printers stay cheap to call from any command module.
    _console = Console()

    @classmethod
    def ok(cls, msg: str) -> None:
        """Successful step (file copied, action completed)."""
        cls._console.print(f"[green]\\[ok][/green]    {msg}")

    @classmethod
    def skip(cls, msg: str) -> None:
        """Step intentionally skipped (idempotent re-run, already-present target)."""
        cls._console.print(f"[yellow]\\[skip][/yellow]  {msg}")

    @classmethod
    def warn(cls, msg: str) -> None:
        """Recoverable issue worth surfacing (missing dep, unknown spec) but not fatal."""
        cls._console.print(f"[yellow]\\[warn][/yellow]  {msg}")

    @classmethod
    def err(cls, msg: str) -> None:
        """Failure that aborts the action — typically followed by ``sys.exit(1)``."""
        cls._console.print(f"[red]\\[err][/red]   {msg}")

    @classmethod
    def info(cls, msg: str) -> None:
        """Neutral progress line (analyzing, importing, summarizing)."""
        cls._console.print(f"[cyan]\\[info][/cyan]  {msg}")
