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

"""Tests for normal and signal-driven Network Consultant cleanup."""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import TestCase


class TestConsultantCleanup(TestCase):
    """Verify Consultant cleanup preserves the filesystem across termination paths."""

    FIXTURE_TEXT = textwrap.dedent(
        """\
        {
            "agent": "demo",
            "success_ratio": "3/3",
            "interactions": []
        }
        """
    )

    def setUp(self) -> None:
        """Create one isolated cleanup directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated cleanup directory after each test."""
        shutil.rmtree(self.tmp_path)

    def _run_child(self, body: str) -> subprocess.CompletedProcess[str]:
        """
        Exercise signal cleanup in a child process that may terminate immediately.

        :param body: The Python source executed by the child process.
        :return: The completed child-process result.
        """
        script = self.tmp_path / "child.py"
        preamble = (
            f"import os, signal, sys\nsys.path.insert(0, {str(os.getcwd())!r})\n"
            "from neuro_san_studio.agent_network_consultant.consultant_cleanup import ConsultantCleanup\n"
            "from neuro_san_studio.agent_network_consultant.fixture_ratio_manager import FixtureRatioManager\n"
        )
        script.write_text(preamble + textwrap.dedent(body), encoding="utf-8")
        return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60, check=False)

    def test_sigterm_restores_bumped_ratios(self) -> None:
        """Restore temporarily raised fixture ratios before SIGTERM exits the process."""
        fixture = self.tmp_path / "a.hocon"
        fixture.write_text(self.FIXTURE_TEXT, encoding="utf-8")

        result = self._run_child(
            textwrap.dedent(
                f"""\
                ConsultantCleanup.configure({{}})
                ConsultantCleanup.remember_ratios({{{str(fixture)!r}: "1/1"}})
                signal.signal(signal.SIGTERM, ConsultantCleanup.handle_sigterm)
                os.kill(os.getpid(), signal.SIGTERM)
                sys.exit(0)
                """
            ),
        )

        self.assertEqual(128 + signal.SIGTERM, result.returncode, result.stderr)
        self.assertIn('"success_ratio": "1/1"', fixture.read_text(encoding="utf-8"))

    def test_default_sigterm_does_not_unwind_finally(self) -> None:
        """Demonstrate why Consultant installs explicit signal cleanup."""
        fixture = self.tmp_path / "b.hocon"
        fixture.write_text(self.FIXTURE_TEXT, encoding="utf-8")

        result = self._run_child(
            textwrap.dedent(
                f"""\
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                finally:
                    FixtureRatioManager.restore({{{str(fixture)!r}: "1/1"}})
                """
            ),
        )

        self.assertEqual(-signal.SIGTERM, result.returncode)
        self.assertIn('"success_ratio": "3/3"', fixture.read_text(encoding="utf-8"))
