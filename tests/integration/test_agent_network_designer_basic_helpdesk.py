# Copyright (C) 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""
End-to-end smoke test for Agent Network Designer (AND):
1) AND generates basic_helpdesk network from a deterministic prompt
2) Fixture test validates the generated network's responses using keywords + gist

Two test options are provided:
    - test_and_generates_basic_helpdesk_direct:
        Uses "direct" mode (in-process, no server required).
        Concurrency is controlled by success_ratio in the fixture HOCON.
        In direct mode, use_direct=True must be passed to
        AgentSessionFactory.create_session() so that AND can access external
        tools like agent_network_editor locally. This is the programmatic
        equivalent of the --local_externals_direct flag in agent_cli.

    - test_and_generates_basic_helpdesk_mcp:
        Uses "mcp" mode (connects to a running neuro-san server).
        Concurrency is controlled by success_ratio in the fixture HOCON.
        In mcp mode, --local_externals_direct is NOT needed because the
        server handles tool resolution on its own.
        Requires a running server: python -m run --server-only

SimpleOneShot cannot be used for AND generation because it does not expose
the use_direct parameter. The streaming logic below replicates
SimpleOneShot.get_answer_for() with use_direct=True added to the session
creation.

How to run:
    Prerequisites:
        export PYTHONPATH=$(pwd)
        export AGENT_TOOL_PATH=coded_tools/
        export AGENT_MANIFEST_FILE=registries/manifest.hocon

    Option 1 - Direct mode (no server required):
        pytest -s -v -k "test_and_generates_basic_helpdesk_direct" \
            tests/integration/test_agent_network_designer_basic_helpdesk.py \
            2>&1 | tee test_output.log

    Option 2 - MCP mode (requires running server first):
        python -m run --server-only  # in a separate terminal
        pytest -s -v -k "test_and_generates_basic_helpdesk_mcp" \
            tests/integration/test_agent_network_designer_basic_helpdesk.py \
            2>&1 | tee test_output.log

    Run both:
        pytest -s -v -m "integration_and_smoke" \
            tests/integration/test_agent_network_designer_basic_helpdesk.py \
            2>&1 | tee test_output.log

    Adjust concurrency:
        Edit success_ratio in the fixture HOCON files:
        - tests/fixtures/generated/basic_helpdesk_test_direct.hocon
        - tests/fixtures/generated/basic_helpdesk_test_mcp.hocon
        e.g., "1/1" for single run, "5/5" for 5 concurrent, "10/10" for 10 concurrent
        Note: 1/1 is recommended for CI right now other concurrency levels require a little more tuning to be stable.
"""

import os
from typing import Any
from typing import Dict
from unittest import TestCase

import pytest
from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.interfaces.agent_session import AgentSession
from neuro_san.message_processing.basic_message_processor import BasicMessageProcessor
from neuro_san.test.unittest.dynamic_hocon_unit_tests import DynamicHoconUnitTests


class TestAgentNetworkDesignerBasicHelpdesk(TestCase):
    """
    Data-driven end-to-end smoke test:
    Step 1 - AND generates basic_helpdesk network
    Step 2 - Fixture test validates the generated network's responses

    Two test methods are provided as options:
    - direct: in-process, no server required (basic_helpdesk_test_direct.hocon)
    - mcp: via running server, for concurrent load testing (basic_helpdesk_test_mcp.hocon)
    """

    DYNAMIC = DynamicHoconUnitTests(__file__, path_to_basis="../fixtures")

    AND_PROMPT = (
        'Create a network called "basic_helpdesk" with exactly 3 agents '
        "and no toolbox, subnetwork, or MCP tools. "
        'Structure: "helpdesk_manager" is the frontman (top-level agent). '
        "It delegates to 2 leaf agents. "
        '"technical_support" handles technical troubleshooting inquiries '
        "(e.g., connectivity, software issues). "
        '"billing_support" handles billing and account inquiries '
        "(e.g., invoices, payments, subscriptions). "
        "There are no mid-level agents. The frontman connects directly "
        "to both leaf agents. No additional agents should be added."
    )

    def _generate_basic_helpdesk(self):
        """
        Use AND to generate the basic_helpdesk network and verify
        the HOCON file was created on disk.

        Uses direct mode with use_direct=True so AND can access the
        agent_network_editor tool. See module docstring for details.
        """
        session: AgentSession = AgentSessionFactory().create_session(
            "direct", "agent_network_designer"
        )
        input_processor = StreamingInputProcessor(session=session)
        processor: BasicMessageProcessor = input_processor.get_message_processor()
        request: Dict[str, Any] = input_processor.formulate_chat_request(self.AND_PROMPT)

        empty: Dict[str, Any] = {}
        for chat_response in session.streaming_chat(request):
            message: Dict[str, Any] = chat_response.get("response", empty)
            processor.process_message(message, chat_response.get("type"))

        answer: str = processor.get_compiled_answer()
        self.assertIsNotNone(answer)
        self.assertGreater(len(answer), 0)

        # Verify file was created
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        hocon_path = os.path.join(repo_root, "registries", "generated", "basic_helpdesk.hocon")
        self.assertTrue(
            os.path.exists(hocon_path),
            f"AND did not generate {hocon_path}",
        )

    @pytest.mark.timeout(600)
    @pytest.mark.integration
    @pytest.mark.integration_and_smoke
    def test_and_generates_basic_helpdesk_direct(self):
        """
        Option 1: Direct mode (in-process, no server required).
        Step 1: AND generates the basic_helpdesk network.
        Step 2: Verify the HOCON file exists on disk.
        Step 3: Run the direct fixture test (concurrency set in HOCON success_ratio).
        """
        self._generate_basic_helpdesk()

        self.DYNAMIC.one_test_hocon(
            self,
            "generated_basic_helpdesk_test_direct",
            "generated/basic_helpdesk_test_direct.hocon",
        )

    @pytest.mark.timeout(600)
    @pytest.mark.integration
    @pytest.mark.integration_and_smoke
    def test_and_generates_basic_helpdesk_mcp(self):
        """
        Option 2: MCP mode (requires a running neuro-san server).
        Step 1: AND generates the basic_helpdesk network.
        Step 2: Verify the HOCON file exists on disk.
        Step 3: Run the mcp fixture test (concurrent load testing, set in HOCON success_ratio).
        Requires: python -m run --server-only
        """
        self._generate_basic_helpdesk()

        self.DYNAMIC.one_test_hocon(
            self,
            "generated_basic_helpdesk_test_mcp",
            "generated/basic_helpdesk_test_mcp.hocon",
        )
