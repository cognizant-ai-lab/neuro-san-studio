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

"""End-to-end direct and MCP verification for Agent Network Consultant repairs.

Run the direct case without a server:
    pytest -s -v -k "test_consultant_repairs_health_check_direct" \
        tests/integration/test_agent_network_consultant_health_check.py

Run the MCP case after starting the server with `python -m neuro_san_studio run --server-only`:
    pytest -s -v -k "test_consultant_repairs_health_check_mcp" \
        tests/integration/test_agent_network_consultant_health_check.py
"""

import signal
from pathlib import Path
from typing import Any
from unittest import TestCase

import pytest
from neuro_san.test.unittest.dynamic_hocon_unit_tests import DynamicHoconUnitTests
from typing_extensions import override

from coded_tools.agent_network_consultant.network_scratchpad import SCRATCHPAD_DIR
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.network_consultant_orchestrator import NetworkConsultantOrchestrator


class TestAgentNetworkConsultantHealthCheck(TestCase):
    """Repair one isolated network and verify the result through both supported fixture transports."""

    DYNAMIC = DynamicHoconUnitTests(__file__, path_to_basis="../fixtures")
    REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
    RESOURCE_DIRECTORY = Path(__file__).resolve().parent / "resources" / "agent_network_consultant"
    NETWORK_TEMPLATE = RESOURCE_DIRECTORY / "health_check_network.hocon"
    FIXTURE_TEMPLATE = RESOURCE_DIRECTORY / "health_check_fixture.hocon"
    INTENDED_BEHAVIOR = (
        "Every successful service health-check response must state that the service is operational and end with "
        "the exact verification token GREEN-CHECK. Preserve the existing two-agent delegation."
    )

    @override
    def setUp(self) -> None:
        """Prepare cleanup tracking without touching an existing generated network."""
        self._created_files: list[Path] = []
        self._created_directories: list[Path] = []
        self._previous_sigterm_handler: Any = signal.getsignal(signal.SIGTERM)

    @override
    def tearDown(self) -> None:
        """Remove only paths created by the current test and restore the process signal handler."""
        signal.signal(signal.SIGTERM, self._previous_sigterm_handler)
        for path in reversed(self._created_files):
            path.unlink(missing_ok=True)
        for path in reversed(self._created_directories):
            path.rmdir()

    def _write_new_file(self, path: Path, content: str) -> None:
        """
        Write a test-owned file after refusing to replace existing data.

        :param path: The new file path.
        :param content: The file content.
        """
        if path.exists():
            self.fail(f"Integration test refuses to replace existing path: {path}")
        path.write_text(content, encoding="utf-8")
        self._created_files.append(path)

    def _prepare_target(self, network_name: str) -> tuple[str, str, Path, Path, str]:
        """
        Create an isolated generated network and its deliberately failing direct fixture.

        :param network_name: The unique generated network basename.
        :return: The HOCON reference, fixture reference, network path, fixture path, and original network text.
        """
        hocon_reference = f"generated/{network_name}.hocon"
        network_path = self.REPOSITORY_ROOT / "registries" / hocon_reference
        network_directory = network_path.parent
        if not network_directory.exists():
            network_directory.mkdir()
            self._created_directories.append(network_directory)
        fixture_directory = self.REPOSITORY_ROOT / "tests" / "fixtures" / "generated" / network_name
        if fixture_directory.exists():
            self.fail(f"Integration test refuses to reuse existing directory: {fixture_directory}")
        fixture_directory.mkdir()
        self._created_directories.append(fixture_directory)
        fixture_path = fixture_directory / "health_check.hocon"

        network_text = self.NETWORK_TEMPLATE.read_text(encoding="utf-8")
        fixture_text = self.FIXTURE_TEMPLATE.read_text(encoding="utf-8")
        fixture_text = fixture_text.replace("__NETWORK_NAME__", network_name).replace("__CONNECTION__", "direct")
        self._write_new_file(network_path, network_text)
        self._write_new_file(fixture_path, fixture_text)
        return (
            hocon_reference,
            f"generated/{network_name}/health_check.hocon",
            network_path,
            fixture_path,
            network_text,
        )

    def _repair_and_verify(self, network_name: str, final_connection: str) -> None:
        """
        Run Consultant against a failing direct fixture and verify the repaired network.

        :param network_name: The unique generated network basename.
        :param final_connection: The fixture transport used for final verification.
        """
        hocon_reference, fixture_reference, network_path, fixture_path, original_text = self._prepare_target(
            network_name
        )
        try:
            NetworkConsultantOrchestrator.run(
                ConsultantOptions(
                    hocon_file=hocon_reference,
                    direction=self.INTENDED_BEHAVIOR,
                    max_iterations=3,
                    success_ratio="1/1",
                )
            )

            repaired_text = network_path.read_text(encoding="utf-8")
            self.assertNotEqual(original_text, repaired_text)
            self.assertIn("GREEN-CHECK", repaired_text)

            fixture_text = fixture_path.read_text(encoding="utf-8")
            fixture_path.write_text(fixture_text.replace('"direct"', f'"{final_connection}"'), encoding="utf-8")
            self.DYNAMIC.one_test_hocon(self, f"consultant_health_check_{final_connection}", fixture_reference)
        finally:
            for scratchpad_path in SCRATCHPAD_DIR.glob(f"{network_name}.*.txt"):
                scratchpad_path.unlink(missing_ok=True)

    @pytest.mark.timeout(1200)
    @pytest.mark.integration
    @pytest.mark.integration_agent_network_consultant
    def test_consultant_repairs_health_check_direct(self) -> None:
        """Repair through Consultant and verify the result in-process without a server."""
        self._repair_and_verify("consultant_integration_direct", "direct")

    @pytest.mark.timeout(1200)
    @pytest.mark.integration
    @pytest.mark.integration_agent_network_consultant
    def test_consultant_repairs_health_check_mcp(self) -> None:
        """Repair through Consultant and verify the result through a running MCP server."""
        self._repair_and_verify("consultant_integration_mcp", "mcp")
