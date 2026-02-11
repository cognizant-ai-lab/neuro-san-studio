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

"""
Simple ServiceNow Agents Integration Test Script

This script tests the ServiceNow agents integration with the provided credentials.
"""

import os
import sys
import traceback
from pathlib import Path

import requests
from dotenv import load_dotenv

from coded_tools.tools.now_agents.nowagent_api_get_agents import NowAgentAPIGetAgents

# Add the project root to Python path (need to go up 5 levels:
# integration_tests -> now_agents -> coded_tools -> tests ->
# project_root)
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def load_environment():
    """Load environment variables from .env file"""
    env_path = project_root / ".env"
    if not env_path.exists():
        print("ERROR: .env file not found!")
        return False

    load_dotenv(env_path)

    # Check key variables
    required_vars = ["SERVICENOW_INSTANCE_URL", "SERVICENOW_USER", "SERVICENOW_PWD"]

    for var in required_vars:
        if not os.getenv(var):
            print(f"ERROR: Missing {var}")
            return False

    print("SUCCESS: Environment variables loaded")
    return True


def test_connectivity():
    """Test basic ServiceNow connectivity"""
    print("\nTesting ServiceNow connectivity...")

    try:

        base_url = os.getenv("SERVICENOW_INSTANCE_URL")
        user = os.getenv("SERVICENOW_USER")
        pwd = os.getenv("SERVICENOW_PWD")

        # Simple test API call
        test_url = f"{base_url}api/now/table/sys_user?sysparm_limit=1"
        response = requests.get(test_url, auth=(user, pwd), headers={"Accept": "application/json"}, timeout=30)

        if response.status_code == 200:
            print(f"SUCCESS: Connected to {base_url}")
            return True

        print(f"ERROR: Connection failed - Status {response.status_code}")
        print(f"Response: {response.text}")
        return False

    except requests.RequestException as e:
        print(f"ERROR: Connection test failed - {str(e)}")
        return False


def test_agent_discovery():
    """Test ServiceNow AI agents discovery"""
    print("\nTesting ServiceNow AI agent discovery...")

    try:
        get_agents_tool = NowAgentAPIGetAgents()

        args = {"inquiry": "test discovery"}
        sly_data = {}

        result = get_agents_tool.invoke(args, sly_data)

        print(f"Raw result: {result}")

        if isinstance(result, dict) and "result" in result:
            agents = result["result"]
            if isinstance(agents, list):
                print(f"SUCCESS: Found {len(agents)} ServiceNow AI agents")

                for i, agent in enumerate(agents, 1):
                    name = agent.get("name", "Unknown")
                    description = agent.get("description", "No description")
                    sys_id = agent.get("sys_id", "No ID")
                    print(f"  Agent {i}: {name}")
                    print(f"    Description: {description}")
                    print(f"    ID: {sys_id}")

                return agents

            print("ERROR: No agents found or invalid format")
            return []

        print("ERROR: Invalid response format")
        return []

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR: Agent discovery failed - {str(e)}")
        traceback.print_exc()
        return []


def main():
    """Run tests"""
    print("ServiceNow Agents Integration Test")
    print("=" * 40)

    # Test 1: Load environment
    if not load_environment():
        return

    # Test 2: Test connectivity
    if not test_connectivity():
        return

    # Test 3: Test agent discovery
    agents = test_agent_discovery()

    print("\n" + "=" * 40)
    print("Test Summary:")
    print("- Environment: OK")
    print("- Connectivity: OK")
    print(f"- Agents found: {len(agents)}")

    if agents:
        print("\nAgents are available for interaction!")
    else:
        print("\nNo agents found - check ServiceNow configuration")


if __name__ == "__main__":
    main()
