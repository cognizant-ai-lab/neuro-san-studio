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

"""Stopping a run must not leave CONFIDENT_FIX success_ratio bumps on disk.

nsflow's Stop sends SIGTERM. Python's default disposition terminates without unwinding, so
main()'s `finally` never runs -- these pin the handler that replaces it.
"""

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner

FIXTURE = textwrap.dedent(
    """\
    {
        "agent": "demo",
        "success_ratio": "3/3",
        "interactions": []
    }
    """
)


class TestStopRestoresRatios:
    """Test stop restores ratios."""

    @staticmethod
    def _run_child(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
        """Exercise the real handler in a real process -- a SIGTERM's effect on `finally` is
        precisely what an in-process fake would paper over."""
        script = tmp_path / "child.py"
        preamble = (
            f"import os, signal, sys\nsys.path.insert(0, {str(os.getcwd())!r})\n"
            "from neuro_san_studio.network_consultant.consultant_workflow import ConsultantWorkflow\n"
            "from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner\n"
        )
        # Composed, not dedented after interpolation: dedent on an already-substituted template
        # finds an empty common prefix and strips nothing.
        script.write_text(preamble + textwrap.dedent(body), encoding="utf-8")
        return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60, check=False)

    @staticmethod
    def test_sigterm_restores_bumped_ratios(tmp_path: Path) -> None:
        """SIGTERM restores ratios before terminating the process."""
        fixture = tmp_path / "a.hocon"
        fixture.write_text(FIXTURE, encoding="utf-8")

        result = TestStopRestoresRatios._run_child(
            tmp_path,
            textwrap.dedent(
                f"""\
                ConsultantWorkflow.cleanup_state.update({{"original_ratios": {{{str(fixture)!r}: "1/1"}}}})
                signal.signal(signal.SIGTERM, ConsultantWorkflow.handle_sigterm)
                os.kill(os.getpid(), signal.SIGTERM)
                # Only reached if the handler failed to exit.
                sys.exit(0)
                """
            ),
        )

        assert result.returncode == 128 + signal.SIGTERM, result.stderr
        assert '"success_ratio": "1/1"' in fixture.read_text(encoding="utf-8")

    @staticmethod
    def test_default_sigterm_would_not_have_restored_them(tmp_path: Path) -> None:
        """The bug this guards: without the handler, `finally` does not run on SIGTERM."""
        fixture = tmp_path / "b.hocon"
        fixture.write_text(FIXTURE, encoding="utf-8")

        result = TestStopRestoresRatios._run_child(
            tmp_path,
            textwrap.dedent(
                f"""\
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                finally:
                    FixtureRunner.restore_success_ratios({{{str(fixture)!r}: "1/1"}})
                """
            ),
        )

        assert result.returncode == -signal.SIGTERM
        assert '"success_ratio": "3/3"' in fixture.read_text(encoding="utf-8")

    @staticmethod
    def test_one_unreadable_fixture_does_not_abandon_the_others(tmp_path: Path) -> None:
        """Restoring runs from a `finally` and from the SIGTERM handler. Raising partway would
        leave every later fixture bumped, and from the `finally` would mask the real error."""
        good = tmp_path / "good.hocon"
        good.write_text(FIXTURE, encoding="utf-8")
        missing = tmp_path / "deleted-mid-run.hocon"

        FixtureRunner.restore_success_ratios({str(missing): "1/1", str(good): "1/1"})

        assert '"success_ratio": "1/1"' in good.read_text(encoding="utf-8")
