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

"""Environment defaults required before Network Consultant framework imports."""

import os

import neuro_san_studio


class ConsultantEnvironment:
    """Configure direct-session and fixture defaults without overwriting user settings."""

    @staticmethod
    def toolbox_directory() -> str:
        """Return the installed Studio toolbox directory."""
        return os.path.join(os.path.dirname(neuro_san_studio.__file__), "toolbox")

    @classmethod
    def configure(cls) -> None:
        """Set defaults that neuro-san reads while its modules are imported."""
        toolbox_directory = cls.toolbox_directory()
        os.environ.setdefault("AGENT_MANIFEST_FILE", "registries/manifest.hocon")
        os.environ.setdefault("AGENT_TOOL_PATH", "coded_tools")
        os.environ.setdefault("AGENT_TOOLBOX_INFO_FILE", os.path.join(toolbox_directory, "toolbox_info.hocon"))
        os.environ.setdefault(
            "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE",
            os.path.join(toolbox_directory, "agent_network_designer_toolbox_info.hocon"),
        )
        os.environ.setdefault("AGENT_TEST_THINKING_BASIS", "/tmp/network_consultant_test_thinking")
