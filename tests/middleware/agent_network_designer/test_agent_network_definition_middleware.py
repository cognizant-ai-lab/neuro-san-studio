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

"""Tests for AgentNetworkDefinitionMiddleware path resolution."""

import os
from unittest.mock import patch

from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware


class TestAgentNetworkDefinitionMiddleware:
    """Tests for AgentNetworkDefinitionMiddleware._resolve_hocon_path."""

    # Tests for AGENT_MANIFEST_FILE parsing, mirroring the persistor's parsing tests
    # so loads and saves stay in agreement on file location.

    def test_resolve_splits_manifest_env_var_on_pathsep(self) -> None:
        """
        _resolve_hocon_path derives base_dir from the first entry of an os.pathsep-separated AGENT_MANIFEST_FILE.
        """
        first_manifest: str = os.path.join("first_dir", "manifest.hocon")
        second_manifest: str = os.path.join("second_dir", "manifest.hocon")
        env_value: str = os.pathsep.join([first_manifest, second_manifest])
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            middleware = AgentNetworkDefinitionMiddleware(sly_data={})
            # The input must not exist relative to cwd, so resolution falls through to base_dir.
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        assert resolved == "first_dir/generated/does_not_exist.hocon"

    def test_resolve_skips_empty_leading_entry(self) -> None:
        """
        _resolve_hocon_path uses the first non-empty entry when AGENT_MANIFEST_FILE has a leading separator.
        """
        env_value: str = os.pathsep + os.path.join("first_dir", "manifest.hocon")
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            middleware = AgentNetworkDefinitionMiddleware(sly_data={})
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        assert resolved == "first_dir/generated/does_not_exist.hocon"

    def test_resolve_defaults_when_manifest_env_var_empty(self) -> None:
        """
        _resolve_hocon_path falls back to the default registries dir when AGENT_MANIFEST_FILE is empty.
        """
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": ""}):
            middleware = AgentNetworkDefinitionMiddleware(sly_data={})
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        assert resolved == "registries/generated/does_not_exist.hocon"
