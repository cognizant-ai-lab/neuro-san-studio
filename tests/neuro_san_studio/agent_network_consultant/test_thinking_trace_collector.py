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

"""Tests for filtered fixture thinking-trace consolidation."""

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestThinkingTraceCollector(TestCase):
    """Verify diagnostic traces retain one useful iteration without prompts or telemetry."""

    TRACE = """Agent: /worker
[SYSTEM] @ now:
private system instructions

[AI] @ now:
useful reasoning

```json
{"prompt_tokens": 10, "total_cost": 1}
```
"""

    def test_strip_system_entries_filters_private_and_accounting_content(self) -> None:
        """Retain agent reasoning while removing system prompts and cost telemetry."""
        collector = ThinkingTraceCollector("run-one", basis_directory="")

        filtered = collector.strip_system_entries(self.TRACE.partition("\n")[2])

        self.assertIn("useful reasoning", filtered)
        self.assertNotIn("private system instructions", filtered)
        self.assertNotIn("prompt_tokens", filtered)

    def test_write_filters_noise_and_later_iterations(self) -> None:
        """Write useful reasoning from only the earliest success-ratio iteration."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            basis = root / "raw"
            output = root / "output"
            first_iteration = basis / "turn_fixture.hocon_0"
            later_iteration = basis / "turn_fixture.hocon_1"
            first_iteration.mkdir(parents=True)
            later_iteration.mkdir(parents=True)
            (first_iteration / "worker.txt").write_text(self.TRACE, encoding="utf-8")
            (later_iteration / "worker.txt").write_text(
                self.TRACE.replace("useful reasoning", "later retry"), encoding="utf-8"
            )
            collector = ThinkingTraceCollector("run-one", basis_directory=basis, output_directory=output)

            collector.write("fixture.hocon", 0.0)

            consolidated = (output / "run-one" / "fixture.hocon.txt").read_text(encoding="utf-8")

        self.assertIn("--- /worker ---", consolidated)
        self.assertIn("useful reasoning", consolidated)
        self.assertNotIn("private system instructions", consolidated)
        self.assertNotIn("prompt_tokens", consolidated)
        self.assertNotIn("later retry", consolidated)

    def test_write_redacts_credentials_before_persisting_a_trace(self) -> None:
        """Prevent filtered diagnostic traces from persisting credentials found in model content."""
        secret = "sk-proj-thinking-trace-secret"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            basis = root / "raw"
            output = root / "output"
            run_directory = basis / "turn_fixture.hocon_0"
            run_directory.mkdir(parents=True)
            trace = self.TRACE.replace("useful reasoning", f"OPENAI_API_KEY={secret}")
            (run_directory / "worker.txt").write_text(trace, encoding="utf-8")
            collector = ThinkingTraceCollector("run-one", basis_directory=basis, output_directory=output)

            collector.write("fixture.hocon", 0.0)

            consolidated = (output / "run-one" / "fixture.hocon.txt").read_text(encoding="utf-8")

        self.assertNotIn(secret, consolidated)
        self.assertIn("[REDACTED]", consolidated)

    def test_write_without_trace_configuration_is_a_no_op(self) -> None:
        """Create no output when raw thinking capture is disabled."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            collector = ThinkingTraceCollector("run-one", basis_directory="", output_directory=output)

            collector.write("fixture.hocon", 0.0)

            self.assertFalse(output.exists())

    def test_run_directory_isolates_runs_and_rejects_unsafe_identifiers(self) -> None:
        """Resolve separate run directories without permitting path traversal."""
        first = ThinkingTraceCollector("run-one", basis_directory="").run_directory()
        second = ThinkingTraceCollector("run-two", basis_directory="").run_directory()

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith(os.path.join("improvement", "run-one")))
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            ThinkingTraceCollector("../another-run", basis_directory="")
