#!/usr/bin/env python3
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

"""Test ServiceNow agents directly with more debugging"""

import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

from coded_tools.tools.now_agents.nowagent_api_get_agents import NowAgentAPIGetAgents

# Add the project root to Python path (need to go up 5 levels:
# integration_tests -> now_agents -> coded_tools -> tests ->
# project_root)
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment
env_path = project_root / ".env"
load_dotenv(env_path)


def test_agents_with_debug():
    """Test ServiceNow agents discovery with debugging information."""
    print("Testing ServiceNow Agents Discovery with Debug Info")
    print("=" * 55)

    # Create the tool
    get_agents_tool = NowAgentAPIGetAgents()

    # Test with debug
    args = {"inquiry": "Show me available agents"}
    sly_data = {}

    print("Calling NowAgentAPIGetAgents.invoke()...")
    print("Args:", args)
    print("Sly data:", sly_data)
    print()

    try:
        result = get_agents_tool.invoke(args, sly_data)
        print("RESULT:")
        print(result)
        print()
        print("RESULT TYPE:", type(result))

        # Try to parse the result
        if isinstance(result, dict):
            if "error" in result:
                print("ERROR in response:", result["error"])
            if "result" in result:
                print("AGENTS FOUND:", len(result["result"]) if isinstance(result["result"], list) else "Not a list")

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"EXCEPTION: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    test_agents_with_debug()
