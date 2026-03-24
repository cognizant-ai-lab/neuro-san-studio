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
import sys

from plugins.llm_config_validator.check_llm_configs import run_checks


class LlmConfigValidatorPlugin:  # pylint: disable=too-few-public-methods
    """
    Validates LLM configurations from a HOCON file before server startup.

    Supports both agent network HOCON files (with "tools") and standalone
    studio llm_config files.  Exits with a non-zero code when any
    configuration fails, so startup is blocked on broken LLM setups.
    """

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
        print(f"\n[LlmConfigValidator] Checking LLM configs in: {hocon_path}\n")
        success: bool = asyncio.run(run_checks(hocon_path))
        if not success:
            sys.exit(1)
