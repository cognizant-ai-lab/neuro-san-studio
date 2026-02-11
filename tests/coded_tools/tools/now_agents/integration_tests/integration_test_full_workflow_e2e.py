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
ServiceNow Agents Integration Test Script

This script tests the ServiceNow agents integration with the provided credentials.
It validates connectivity, agent discovery, and basic interaction functionality.
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from coded_tools.tools.now_agents.nowagent_api_get_agents import NowAgentAPIGetAgents
from coded_tools.tools.now_agents.nowagent_api_retrieve_message import NowAgentRetrieveMessage
from coded_tools.tools.now_agents.nowagent_api_send_message import NowAgentSendMessage

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

    # Verify required environment variables
    required_vars = [
        "SERVICENOW_INSTANCE_URL",
        "SERVICENOW_USER",
        "SERVICENOW_PWD",
        "SERVICENOW_CALLER_EMAIL",
        "SERVICENOW_GET_AGENTS_QUERY",
    ]

    missing_vars = []
    for var in required_vars:
        if os.getenv(var) is None:
            missing_vars.append(var)

    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        return False

    print("SUCCESS: Environment variables loaded successfully")
    return True


def test_basic_connectivity():
    """Test basic connectivity to ServiceNow instance"""
    print("\n[TEST] Testing basic connectivity to ServiceNow...")

    try:

        base_url = os.getenv("SERVICENOW_INSTANCE_URL")
        user = os.getenv("SERVICENOW_USER")
        pwd = os.getenv("SERVICENOW_PWD")

        # Test basic authentication with a simple API call
        test_url = f"{base_url}api/now/table/sys_user?sysparm_limit=1"
        response = requests.get(test_url, auth=(user, pwd), headers={"Accept": "application/json"}, timeout=30)

        if response.status_code == 200:
            print(f"SUCCESS: Successfully connected to ServiceNow instance: {base_url}")
            return True

        print(f"ERROR: Connection failed with status code: {response.status_code}")
        print(f"Response: {response.text}")
        return False

    except requests.RequestException as e:
        print(f"ERROR: Connection test failed: {str(e)}")
        return False


def test_agent_discovery():
    """Test ServiceNow AI agents discovery"""
    print("\n[TEST] Testing ServiceNow AI agent discovery...")

    try:
        get_agents_tool = NowAgentAPIGetAgents()

        # Test agent discovery
        args = {"inquiry": "test discovery"}
        sly_data = {}

        result = get_agents_tool.invoke(args, sly_data)

        if isinstance(result, dict) and "result" in result:
            agents = result["result"]
            if isinstance(agents, list):
                print(f"SUCCESS: Successfully discovered {len(agents)} ServiceNow AI agents")

                # Display discovered agents
                for i, agent in enumerate(agents, 1):
                    name = agent.get("name", "Unknown")
                    description = agent.get("description", "No description")
                    sys_id = agent.get("sys_id", "No ID")
                    print(f"   {i}. Agent: {name}")
                    print(f"      Description: {description}")
                    print(f"      ID: {sys_id}")
                    print()

                return agents

            print("ERROR: No agents found or invalid response format")
            print(f"Result: {result}")
            return []

        print("ERROR: Agent discovery failed - invalid response format")
        print(f"Result: {result}")
        return []

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR: Agent discovery failed: {str(e)}")
        return []


def test_single_agent_interaction(agents):  # pylint: disable=too-many-locals
    """Test single interaction with a ServiceNow agent"""
    if not agents:
        print("\n[WARNING] Skipping agent interaction test - no agents available")
        return False

    print("\n[TEST] Testing single agent interaction...")

    try:
        # Use the first available agent
        selected_agent = agents[0]
        agent_name = selected_agent.get("name", "Unknown")
        agent_id = selected_agent.get("sys_id")

        print(f"Testing with agent: {agent_name} (ID: {agent_id})")

        # Initialize tools
        send_tool = NowAgentSendMessage()
        retrieve_tool = NowAgentRetrieveMessage()

        # Test inquiry (simple question that shouldn't require an existing ticket)
        test_inquiry = "Hello, can you help me understand what services you provide?"

        print(f"Sending inquiry: '{test_inquiry}'")

        # Send message
        send_args = {"inquiry": test_inquiry, "agent_id": agent_id}
        sly_data = {}

        send_result = send_tool.invoke(send_args, sly_data)

        if isinstance(send_result, dict) and "metadata" in send_result:
            print("SUCCESS: Message sent successfully")
            print(f"Session path: {sly_data.get('session_path', 'Not set')}")

            # Try to retrieve response
            retrieve_args = {"inquiry": test_inquiry, "agent_id": agent_id}

            print("Attempting to retrieve response...")
            retrieve_result = retrieve_tool.invoke(retrieve_args, sly_data)

            if isinstance(retrieve_result, dict) and "result" in retrieve_result:
                responses = retrieve_result["result"]
                if responses:
                    print("SUCCESS: Retrieved agent response:")
                    for response in responses:
                        content = response.get("content", "No content")
                        print(f"   Response: {content}")
                    return True

                print("[WARNING] No response received (this might be expected given the limitations)")
                return False

            print("ERROR: Failed to retrieve response")
            print(f"Result: {retrieve_result}")
            return False

        print("ERROR: Failed to send message")
        print(f"Result: {send_result}")
        return False

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR: Agent interaction test failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("ServiceNow Agents Integration Test Suite")
    print("=" * 50)

    # Track test results
    test_results = {}

    # Test 1: Environment setup
    test_results["environment"] = load_environment()

    # Test 2: Basic connectivity
    if test_results["environment"]:
        test_results["connectivity"] = test_basic_connectivity()
    else:
        test_results["connectivity"] = False

    # Test 3: Agent discovery
    if test_results["connectivity"]:
        discovered_agents = test_agent_discovery()
        test_results["discovery"] = len(discovered_agents) > 0
    else:
        discovered_agents = []
        test_results["discovery"] = False

    # Test 4: Single agent interaction
    if test_results["discovery"]:
        test_results["interaction"] = test_single_agent_interaction(discovered_agents)
    else:
        test_results["interaction"] = False

    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)

    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)

    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        print(f"{test_name.upper():15} {status}")

    print(f"\nOVERALL: {passed_tests}/{total_tests} tests passed")

    # Additional notes about limitations
    print("\nNOTES:")
    print("- Most ServiceNow AI agents require existing tickets/records to function properly")
    print("- Current integration supports single interaction only")
    print("- Multi-turn conversations will fail until A2A version is implemented")
    print("- Test failures in interaction may be expected given these limitations")


if __name__ == "__main__":
    main()
