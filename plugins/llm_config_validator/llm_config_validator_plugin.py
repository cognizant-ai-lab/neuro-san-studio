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
script so it can be invoked from run.py via --check-llm-configs.
"""

import asyncio
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from plugins.llm_config_validator.check_llm_configs import create_and_load_llm_factory
from plugins.llm_config_validator.check_llm_configs import extract_llm_configs_from_agent_network
from plugins.llm_config_validator.check_llm_configs import extract_llm_configs_from_studio_config
from plugins.llm_config_validator.check_llm_configs import is_agent_network_hocon
from plugins.llm_config_validator.check_llm_configs import load_agent_network
from plugins.llm_config_validator.check_llm_configs import parse_hocon_file
from plugins.llm_config_validator.check_llm_configs import print_results
from plugins.llm_config_validator.check_llm_configs import test_llm_configs


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

        # --- Step 1: Parse the HOCON file and detect format ---
        print(f"[1] Parsing HOCON file: {hocon_path}")
        try:
            raw_config: Dict[str, Any] = parse_hocon_file(hocon_path)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"    FATAL: Failed to parse HOCON file: {exc}")
            sys.exit(1)

        agent_network_mode: bool = is_agent_network_hocon(raw_config)

        if agent_network_mode:
            print("    Detected format: agent network (has 'tools')")
            try:
                agent_network = load_agent_network(hocon_path)
            except Exception as exc:  # pylint: disable=broad-except
                print(f"    FATAL: Failed to load agent network: {exc}")
                sys.exit(1)
            config: Dict[str, Any] = agent_network.get_config()
            network_name: str = agent_network.get_network_name()
            print(f"    Agent network: {network_name}")
        else:
            print("    Detected format: standalone studio llm_config")
            config = raw_config

        # --- Step 2: Extract all llm_configs ---
        print("[2] Extracting llm_configs...")
        if agent_network_mode:
            llm_configs: List[Tuple[str, Dict[str, Any]]] = extract_llm_configs_from_agent_network(agent_network)
        else:
            llm_configs = extract_llm_configs_from_studio_config(config, hocon_path)

        if not llm_configs:
            print("    No llm_config found in this HOCON file.")
            return

        for label, llm_cfg in llm_configs:
            print(f"    {label:30s} | llm_config: {llm_cfg}")

        # --- Step 3: Create and load the LLM factory ---
        print("[3] Creating LLM factory (loading default_llm_info.hocon)...")
        try:
            llm_factory = create_and_load_llm_factory(config)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"    FATAL: Failed to create/load LLM factory: {exc}")
            sys.exit(1)
        print("    LLM factory loaded successfully.")

        # --- Step 4: Test each unique LLM configuration ---
        print("[4] Testing LLM configuration(s)...\n")
        successes, failures = asyncio.run(test_llm_configs(llm_factory, llm_configs))

        # --- Step 5: Report results ---
        print_results(successes, failures)

        if failures:
            sys.exit(1)
