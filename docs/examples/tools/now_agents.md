# ServiceNow AI Agents

ServiceNow AI Agents is a comprehensive integration system that enables natural language interaction with ServiceNow's Agentic AI platform. It provides discovery, communication, and response retrieval capabilities for over 100+ specialized AI agents within ServiceNow instances.

## Overview

This agent network demonstrates how to integrate with enterprise ServiceNow environments to leverage AI agents for IT service management, HR operations, procurement, incident resolution, and many other business processes. The system follows a three-stage workflow: discover available agents, send inquiries, and retrieve responses.

**Tags:** `tool`, `API`, `ServiceNow`, `Enterprise`

## What You'll Learn

- How to integrate with ServiceNow's Agentic AI APIs
- Enterprise authentication and session management
- Polling-based response retrieval with retry logic
- Comprehensive error handling for enterprise environments
- Unit testing with 100% code coverage
- Integration testing with real ServiceNow instances

## Architecture

The ServiceNow AI Agents integration consists of three main components:

1. **Agent Discovery Tool** (`NowAgentAPIGetAgents`)
   - Queries ServiceNow for available AI agents
   - Returns structured agent metadata (name, description, sys_id)
   - Supports configurable filtering and query parameters

2. **Message Sending Tool** (`NowAgentSendMessage`)  
   - Sends user inquiries to specific ServiceNow AI agents
   - Manages session creation and tracking
   - Handles authentication and request formatting

3. **Response Retrieval Tool** (`NowAgentRetrieveMessage`)
   - Retrieves agent responses using polling with retry logic
   - Implements intelligent backoff strategy
   - Handles asynchronous agent processing

## Prerequisites

### ServiceNow Requirements
- ServiceNow instance (Utah release or later)
- Now Assist Pro Plus or Enterprise licensing
- Agentic AI APIs enabled on the instance
- User account with appropriate permissions:
  - `sn_aia_agent.read` - Read AI agent definitions
  - `sn_aia_external_agent_execution.read` - Read agent interactions
  - `sn_aia_external_agent_execution.create` - Send messages to agents

### Environment Configuration
Set up these environment variables in your `.env` file:

```bash
# ServiceNow Configuration
SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
SERVICENOW_USER="your-username"
SERVICENOW_PWD="your-password"
SERVICENOW_CALLER_EMAIL="caller@company.com"
SERVICENOW_GET_AGENTS_QUERY="active=true"
```

## Usage Examples

### Basic Agent Discovery

```python
from coded_tools.tools.now_agents import NowAgentAPIGetAgents

# Discover available ServiceNow AI agents
get_agents = NowAgentAPIGetAgents()
result = get_agents.invoke({"inquiry": "Show me available agents"}, {})

print(f"Found {len(result['result'])} ServiceNow AI agents:")
for agent in result['result']:
    print(f"- {agent['name']}: {agent['description']}")
```

### Complete Agent Interaction

```python
from coded_tools.tools.now_agents import (
    NowAgentAPIGetAgents,
    NowAgentSendMessage, 
    NowAgentRetrieveMessage
)

# Step 1: Discover agents
get_agents = NowAgentAPIGetAgents()
agents_result = get_agents.invoke({"inquiry": "test"}, {})
agents = agents_result["result"]

if agents:
    # Step 2: Send message to an agent
    send_tool = NowAgentSendMessage()
    sly_data = {}  # Session state management
    
    send_args = {
        "inquiry": "I need help with a password reset request",
        "agent_id": agents[0]["sys_id"]  # Use first available agent
    }
    
    send_result = send_tool.invoke(send_args, sly_data)
    print("Message sent successfully!")
    
    # Step 3: Retrieve agent response
    retrieve_tool = NowAgentRetrieveMessage()
    response_result = retrieve_tool.invoke(send_args, sly_data)
    
    if response_result["result"]:
        print("Agent Response:")
        for response in response_result["result"]:
            print(f"- {response['content']}")
    else:
        print("Agent is still processing or no response available")
```

## Available ServiceNow AI Agents

The system can discover 100+ specialized AI agents including:

- **IT Service Management**: Incident categorization, troubleshooting, resolution
- **HR Operations**: Employee information, policy queries, case management  
- **Procurement**: Product recommendations, purchase orders, sourcing
- **Change Management**: Risk analysis, implementation planning, testing
- **Asset Management**: CI creation, lifecycle management, repair decisions
- **Security**: Vulnerability analysis, compliance reporting, threat assessment
- **Knowledge Management**: Article creation, content consolidation, search
- **Problem Management**: Root cause analysis, investigation, linking

## Testing

The module includes comprehensive testing with 100% code coverage:

### Unit Tests (Fast, Mocked)
```bash
# Run all unit tests
python -m pytest tests/coded_tools/tools/now_agents/unit_tests/ -v

# Generate coverage report  
python -m pytest tests/coded_tools/tools/now_agents/unit_tests/ --cov=coded_tools.tools.now_agents --cov-report=html
```

### Integration Tests (Real ServiceNow API)
```bash
# Test basic connectivity
python tests/coded_tools/tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py

# Test agent discovery
python tests/coded_tools/tools/now_agents/integration_tests/test_integration_agent_discovery_simple.py

# Full end-to-end workflow
python tests/coded_tools/tools/now_agents/integration_tests/test_integration_full_workflow_e2e.py
```

## Key Features

### Enterprise-Grade Integration
- **Authentication**: Secure basic auth with credential management
- **Error Handling**: Comprehensive error detection and recovery
- **Session Management**: Persistent session tracking across API calls
- **Retry Logic**: Intelligent polling with exponential backoff

### Developer Experience
- **100% Test Coverage**: Complete unit and integration test suite
- **Comprehensive Documentation**: Detailed API reference and examples  
- **Clear Separation**: Unit tests (mocked) vs integration tests (real API)
- **Troubleshooting Guide**: Common issues and solutions documented

### Production Readiness
- **Environment Configuration**: Secure credential handling via environment variables
- **Logging**: Detailed debugging output for troubleshooting
- **Performance**: Optimized polling and retry strategies
- **Scalability**: Supports multiple concurrent agent interactions

## Limitations and Considerations

### Agent Dependencies
Most ServiceNow AI agents require existing business context (tickets, incidents, records) to function effectively. Agents may return empty responses if:
- No relevant tickets or records exist
- Agent lacks sufficient context for the inquiry
- Agent requires specific data that's not available

### Session Management
- Session state is managed through the `sly_data` parameter
- Multi-session handling is supported via `sly_data` state persistence
- Session paths are automatically tracked across agent interactions
- Sessions don't persist across application restarts

### Asynchronous Processing
- Some agents may take time to process complex requests
- Polling mechanism handles delays with configurable retry attempts
- Maximum 10 retry attempts with 2-second intervals

## Troubleshooting

### Common Issues

**403 Forbidden Errors:**
```bash
# Test your credentials
python tests/coded_tools/tools/now_agents/integration_tests/debug_servicenow_credentials.py
```

**No Agents Discovered:**
- Verify AI Agents are enabled in ServiceNow
- Check Now Assist licensing status  
- Confirm user permissions for `sn_aia_agent` table

**Empty Agent Responses:**
- Agents may require existing tickets/records for context
- Some agents need specific business data to function
- Consider the agent's intended use case and requirements

## Files Structure

```
coded_tools/tools/now_agents/
├── __init__.py                              # Module exports
├── nowagent_api_get_agents.py              # Agent discovery
├── nowagent_api_send_message.py            # Message sending  
├── nowagent_api_retrieve_message.py        # Response retrieval
└── README.md                               # Complete documentation

registries/
└── now_agents.hocon                         # Agent network configuration

tests/coded_tools/tools/now_agents/
├── unit_tests/                              # Mocked tests (100% coverage)
├── integration_tests/                       # Real API tests
└── README.md                               # Testing guide
```

## Learn More

For complete implementation details, API reference, and advanced configuration options, see the [module documentation](../../../coded_tools/tools/now_agents/README.md).

---

*This example demonstrates enterprise integration patterns, comprehensive testing strategies, and production-ready error handling for ServiceNow environments.*
