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

"""Tests for Agent Network Designer load-tuning settings."""

import asyncio
from pathlib import Path
from typing import Any

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

EXPECTED_TUNING: dict[str, dict[str, int]] = {
    "registries/agent_network_designer.hocon": {
        "max_steps": 10000,
        "max_execution_seconds": 1200,
        "request_timeout_seconds": 1500,
        "max_attempts": 2,
    },
    "registries/agent_network_editor.hocon": {
        "max_steps": 5000,
        "max_execution_seconds": 600,
        "request_timeout_seconds": 750,
        "max_attempts": 2,
    },
    "registries/agent_network_instructions_editor.hocon": {
        "max_steps": 5000,
        "max_execution_seconds": 600,
        "request_timeout_seconds": 750,
        "max_attempts": 2,
    },
    "registries/agent_network_query_generator.hocon": {
        "max_steps": 2000,
        "max_execution_seconds": 300,
        "request_timeout_seconds": 450,
        "max_attempts": 2,
    },
}


async def _restore_config(file_reference: str) -> dict[str, Any]:
    """Restore a HOCON config using the project's normal config restorer."""
    restorer = AbstractAsyncConfigRestorer("agent_network_designer_load_tuning", must_exist=True)
    return await restorer.async_restore(file_reference=file_reference)


def test_agent_network_designer_configs_are_tuned_for_load():
    """AND and its helper networks use bounded load-friendly execution settings."""
    for file_reference, expected_values in EXPECTED_TUNING.items():
        config = asyncio.run(_restore_config(file_reference))

        for key, expected_value in expected_values.items():
            assert config[key] == expected_value, f"{file_reference} should set {key}"

        assert "max_iterations" not in config, f"{file_reference} should use max_steps, not max_iterations"
        assert Path(file_reference).is_file()
