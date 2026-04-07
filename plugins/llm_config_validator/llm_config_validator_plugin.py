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

"""
Plugin wrapper for LLM configuration validation.

Provides a class-based interface around the check_llm_configs diagnostic
script so it can be invoked from run.py via --check-llm-config.
"""

import asyncio
import os
import sys

from neuro_san_studio.interfaces.plugins import BasePlugin
from plugins.llm_config_validator.check_llm_configs import run_checks


class LlmConfigValidatorPlugin(BasePlugin):
    """
    Validates LLM configurations from a HOCON file before server startup.

    Supports both agent network HOCON files (with "tools") and standalone
    studio llm_config files.  Exits with a non-zero code when any
    configuration fails, so startup is blocked on broken LLM setups.
    """

    def __init__(self, args: dict = None):
        """Initialize the LLM config validator plugin.

        Args:
            args: Optional dictionary of arguments for the plugin.
        """
        super().__init__(plugin_name="LlmConfigValidator", args=args)

    def pre_server_start_action(self):
        """Validate LLM configurations when --check-llm-config is specified."""
        hocon_path = self.args.get("check_llm_config")
        if not hocon_path:
            return
        self.check(hocon_path)

    def check(self, hocon_path: str) -> None:
        """
        Parse the given HOCON file, create LLM instances for every unique
        llm_config it contains, invoke each one with a trivial prompt, and
        print a results summary.

        Calls sys.exit(1) if any configuration fails, mirroring the
        behaviour of running check_llm_configs.py directly.

        Args:
            hocon_path: Path to the HOCON file to validate.
        """
        self._logger.info("Checking LLM configs in: %s", hocon_path)
        success: bool = asyncio.run(run_checks(hocon_path))
        if not success:
            sys.exit(1)

    def update_parser_args(self, parser):
        """Add command-line arguments for LLM configuration validation.

        Args:
            parser: The argument parser to update.
        """
        default_llm_config = os.path.join(
            os.getenv("AGENT_MANIFEST_FILE", os.path.join("registries", "manifest.hocon")),
            "..",
            "llm_config.hocon",
        )
        default_llm_config = os.path.normpath(default_llm_config)
        parser.add_argument(
            "--check-llm-config",
            nargs="?",
            const=default_llm_config,
            default=None,
            metavar="HOCON_PATH",
            help="Test every LLM configuration in a HOCON file by creating each "
            "LLM instance and invoking it with a trivial prompt. "
            "Accepts both agent network files (with a 'tools' list, testing each agent's "
            "merged llm_config) and standalone studio llm_config files. "
            "llm_configs that use a 'fallbacks' list are expanded and each model is tested individually. "
            "Duplicate configurations are deduplicated so each unique model is called only once. "
            "Exits with a non-zero code if any configuration fails. "
            f"When passed without a value, defaults to {default_llm_config}.",
        )
