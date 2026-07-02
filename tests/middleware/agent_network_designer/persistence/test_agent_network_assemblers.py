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

"""Tests for Agent Network Designer assemblers."""

import asyncio

from middleware.agent_network_designer.persistence.deployable_agent_network_assembler import (
    DeployableAgentNetworkAssembler,
)
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import DEFAULT_MAX_EXECUTION_SECONDS
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler


def _network_def() -> dict:
    """Return a minimal agent network definition."""
    return {
        "front_desk": {
            "description": "Answers user questions.",
            "instructions": "Route questions to the specialist.",
            "tools": ["specialist"],
        },
        "specialist": {
            "description": "Handles specialist questions.",
            "instructions": "Answer specialist questions.",
        },
    }


def test_hocon_assembler_adds_max_execution_seconds():
    """Generated HOCON networks include the default execution timeout."""
    content = asyncio.run(
        HoconAgentNetworkAssembler(demo_mode=False).assemble_agent_network(
            _network_def(), "front_desk", "support_network", ["How can you help?"]
        )
    )

    assert f'"max_execution_seconds": {DEFAULT_MAX_EXECUTION_SECONDS}' in content


def test_deployable_assembler_adds_max_execution_seconds():
    """Generated deployable networks include the default execution timeout."""
    config = asyncio.run(
        DeployableAgentNetworkAssembler(demo_mode=False).assemble_agent_network(
            _network_def(), "front_desk", "support_network", ["How can you help?"]
        )
    )

    assert config["max_execution_seconds"] == DEFAULT_MAX_EXECUTION_SECONDS
