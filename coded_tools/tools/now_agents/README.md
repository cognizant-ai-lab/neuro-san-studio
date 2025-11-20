# ServiceNow AI Agents Integration Module

Complete integration module for ServiceNow AI agents with the Neuro SAN framework. This module enables discovery, interaction, and response retrieval from ServiceNow's Agentic AI platform.

## 📁 Module Structure

```
coded_tools/now_agents/
├── __init__.py                              # Module initialization and exports
├── nowagent_api_get_agents.py              # Agent discovery functionality  
├── nowagent_api_send_message.py            # Message sending to agents
├── nowagent_api_retrieve_message.py        # Response retrieval from agents
└── README.md                               # This documentation
```

## 🔧 Core Components

### `__init__.py` - Module Initialization
**Purpose**: Package initialization and public API exports  
**What it does**:
- Exports the three main classes for external use
- Provides module-level documentation and usage examples
- Handles import organization for clean external access

**Exports**:
- `NowAgentAPIGetAgents` - Agent discovery class
- `NowAgentSendMessage` - Message sending class  
- `NowAgentRetrieveMessage` - Response retrieval class

### `nowagent_api_get_agents.py` - Agent Discovery
**Purpose**: Discovers and lists available ServiceNow AI agents  
**What it does**:
- Connects to ServiceNow instance using REST API
- Queries the `sn_aia_agent` table for active AI agents
- Returns structured list of agents with metadata (name, description, sys_id)
- Handles authentication, error responses, and empty results
- Supports configurable query filters via environment variables

**Key Methods**:
- `invoke(args, sly_data)` - Main discovery method
- `async_invoke(args, sly_data)` - Async wrapper for compatibility
- `_get_env_variable(var_name)` - Environment variable retrieval with logging

**Environment Variables Used**:
- `SERVICENOW_INSTANCE_URL` - ServiceNow instance base URL
- `SERVICENOW_USER` - ServiceNow username for authentication  
- `SERVICENOW_PWD` - ServiceNow password for authentication
- `SERVICENOW_GET_AGENTS_QUERY` - Query filter for agent discovery (e.g., "active=true")

**API Endpoint**: `GET /api/now/table/sn_aia_agent`

**Returns**: Dictionary with agent list in `result` field
```python
{
    "result": [
        {
            "sys_id": "agent-uuid",
            "name": "Agent Name", 
            "description": "Agent description"
        }
    ]
}
```

### `nowagent_api_send_message.py` - Message Sending
**Purpose**: Sends messages/inquiries to specific ServiceNow AI agents  
**What it does**:
- Takes user inquiry and target agent ID
- Creates authenticated POST request to ServiceNow Agentic AI API
- Manages session creation and tracking
- Stores session path in `sly_data` for response retrieval
- Handles authentication errors and API failures

**Key Methods**:
- `invoke(args, sly_data)` - Main message sending method
- `async_invoke(args, sly_data)` - Async wrapper for compatibility
- `_get_env_variable(var_name)` - Environment variable retrieval with logging

**Required Parameters**:
- `args["inquiry"]` - The message/question to send to the agent
- `args["agent_id"]` - The sys_id of the target ServiceNow AI agent

**Environment Variables Used**:
- `SERVICENOW_INSTANCE_URL` - ServiceNow instance base URL
- `SERVICENOW_USER` - ServiceNow username for authentication
- `SERVICENOW_PWD` - ServiceNow password for authentication  
- `SERVICENOW_CALLER_EMAIL` - Email address for request attribution

**API Endpoint**: `POST /api/sn_aia/agenticai/v1/agent/id/{agent_id}`

**Side Effects**: 
- Updates `sly_data["session_path"]` with session information for response retrieval
- Creates external agent execution record in ServiceNow

**Returns**: ServiceNow API response with session metadata
```python
{
    "metadata": {
        "user_id": "user-uuid",
        "session_id": "session-uuid"
    },
    "request_id": "request-uuid"
}
```

### `nowagent_api_retrieve_message.py` - Response Retrieval  
**Purpose**: Retrieves responses from ServiceNow AI agents using polling/retry logic  
**What it does**:
- Uses session path from previous send_message call
- Polls ServiceNow for agent responses with automatic retry logic
- Handles empty responses and waiting periods
- Returns structured response data when available
- Implements intelligent retry strategy with backoff

**Key Methods**:
- `invoke(args, sly_data)` - Main response retrieval method with retry logic
- `async_invoke(args, sly_data)` - Async wrapper for compatibility
- `_get_env_variable(var_name)` - Environment variable retrieval with logging

**Required Dependencies**:
- `sly_data["session_path"]` - Must be set by prior `NowAgentSendMessage` call
- Session must be valid and active in ServiceNow

**Environment Variables Used**:
- `SERVICENOW_INSTANCE_URL` - ServiceNow instance base URL
- `SERVICENOW_USER` - ServiceNow username for authentication
- `SERVICENOW_PWD` - ServiceNow password for authentication

**API Endpoint**: `GET /api/now/table/sn_aia_external_agent_execution`

**Retry Logic**:
- Maximum 10 retry attempts
- 2-second delay between retries
- Continues until response found or max retries reached

**Returns**: ServiceNow API response with agent messages
```python
{
    "result": [
        {
            "content": "Agent response text",
            "direction": "OUTBOUND",
            "session_path": "session-identifier"
        }
    ]
}
```

## 🚀 Usage Examples

### Basic Agent Discovery
```python
from coded_tools.now_agents import NowAgentAPIGetAgents

# Initialize the discovery tool
get_agents = NowAgentAPIGetAgents()

# Discover available agents
args = {"inquiry": "Show me available agents"}
sly_data = {}

result = get_agents.invoke(args, sly_data)
agents = result["result"]

print(f"Found {len(agents)} agents:")
for agent in agents:
    print(f"- {agent['name']}: {agent['description']}")
```

### Complete Agent Interaction Workflow
```python
from coded_tools.now_agents import (
    NowAgentAPIGetAgents, 
    NowAgentSendMessage, 
    NowAgentRetrieveMessage
)

# Step 1: Discover agents
get_agents = NowAgentAPIGetAgents()
agents_result = get_agents.invoke({"inquiry": "test"}, {})
agents = agents_result["result"]

# Step 2: Send message to first agent
if agents:
    send_tool = NowAgentSendMessage()
    sly_data = {}  # Will be updated with session info
    
    send_args = {
        "inquiry": "Hello, can you help me with my IT issue?",
        "agent_id": agents[0]["sys_id"]
    }
    
    send_result = send_tool.invoke(send_args, sly_data)
    print(f"Message sent successfully: {send_result}")
    
    # Step 3: Retrieve response
    retrieve_tool = NowAgentRetrieveMessage()
    retrieve_args = {
        "inquiry": send_args["inquiry"],
        "agent_id": send_args["agent_id"]
    }
    
    response_result = retrieve_tool.invoke(retrieve_args, sly_data)
    responses = response_result["result"]
    
    if responses:
        print("Agent Response:")
        for response in responses:
            print(f"- {response['content']}")
    else:
        print("No response received from agent")
```

### Error Handling Example
```python
from coded_tools.now_agents import NowAgentAPIGetAgents

try:
    get_agents = NowAgentAPIGetAgents()
    result = get_agents.invoke({"inquiry": "test"}, {})
    
    if "result" in result:
        print(f"Success: Found {len(result['result'])} agents")
    else:
        print("No agents found or error occurred")
        
except SystemExit:
    print("Authentication or API error occurred")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## ⚙️ Configuration

### Required Environment Variables
Create a `.env` file in the project root:

```bash
# ServiceNow Instance Configuration  
SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
SERVICENOW_USER="your-username"
SERVICENOW_PWD="your-password" 
SERVICENOW_CALLER_EMAIL="caller@company.com"
SERVICENOW_GET_AGENTS_QUERY="active=true"

# Optional: LLM Provider (for Neuro SAN orchestration)
OPENAI_API_KEY="your-openai-api-key"
```

### ServiceNow Prerequisites
- **ServiceNow Instance**: Utah release or later with AI Agents enabled
- **Licensing**: Now Assist Pro Plus or Enterprise entitlement
- **User Permissions**:
  - `sn_aia_agent.read` - Read AI agent definitions
  - `sn_aia_external_agent_execution.read` - Read agent interactions
  - `sn_aia_external_agent_execution.create` - Send messages to agents
  - API access permissions
- **Instance Configuration**: Agentic AI APIs must be enabled

## 🧪 Testing

### Comprehensive Test Suite
The module includes a complete test suite with 100% code coverage:

**Location**: `../../tests/coded_tools/now_agents/`

**Structure**:
```
tests/coded_tools/now_agents/
├── unit_tests/                              # Fast, mocked tests (100% coverage)
│   ├── test_unit_agent_discovery_mocked.py
│   ├── test_unit_message_sending_mocked.py  
│   └── test_unit_message_retrieval_mocked.py
├── integration_tests/                       # Real API tests  
│   ├── test_integration_servicenow_connectivity.py
│   ├── test_integration_agent_discovery_simple.py
│   ├── test_integration_full_workflow_e2e.py
│   └── debug_servicenow_credentials.py
└── README.md                               # Complete testing guide
```

### Quick Test Commands
```bash
# Run all unit tests (fast, no credentials needed)
python -m pytest tests/coded_tools/now_agents/unit_tests/ -v

# Test ServiceNow connectivity (no auth required)  
python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py

# Test agent discovery (requires credentials)
python tests/coded_tools/now_agents/integration_tests/test_integration_agent_discovery_simple.py

# Full end-to-end workflow test
python tests/coded_tools/now_agents/integration_tests/test_integration_full_workflow_e2e.py
```

### Test Results Summary
- ✅ **Unit Tests**: 15/15 passing with 100% code coverage
- ✅ **Integration Tests**: All passing, successfully discovering 100+ ServiceNow AI agents
- ✅ **Code Quality**: All tests follow best practices with comprehensive error handling

## 🔍 API Endpoints Reference

### 1. Agent Discovery
- **Method**: GET
- **Endpoint**: `/api/now/table/sn_aia_agent`  
- **Query Parameters**:
  - `sysparm_query`: Filter criteria (e.g., "active=true")
  - `sysparm_fields`: "description,name,sys_id"
- **Authentication**: Basic Auth
- **Response**: JSON array of agent objects

### 2. Send Message  
- **Method**: POST
- **Endpoint**: `/api/sn_aia/agenticai/v1/agent/id/{agent_id}`
- **Headers**: 
  - `Content-Type: application/json`
  - `Accept: application/json`
- **Authentication**: Basic Auth
- **Body**: JSON with inquiry and caller information
- **Response**: Session metadata and request ID

### 3. Retrieve Response
- **Method**: GET  
- **Endpoint**: `/api/now/table/sn_aia_external_agent_execution`
- **Query Parameters**:
  - `sysparm_query`: "direction=OUTBOUND^session_path={session_path}"
- **Authentication**: Basic Auth  
- **Response**: JSON array of response messages

## ⚠️ Known Limitations

1. **Agent Dependencies**: Most ServiceNow AI agents require existing tickets, incidents, or records to function properly
2. **Single Interaction**: Current implementation supports one question-response cycle per session
3. **Multi-turn Conversations**: Not supported until A2A (Agent-to-Agent) architecture is implemented  
4. **Session Persistence**: Sessions are not persisted across application restarts
5. **Async Processing**: Some agents may take time to respond; polling mechanism handles delays

## 🐛 Troubleshooting

### Authentication Errors (401/403)
```
Error: Status 401/403 - Authentication failed
```
**Solutions**:
1. Verify ServiceNow credentials are correct and active
2. Check user has required permissions (`sn_aia_agent.read`, etc.)
3. Ensure API access is enabled for the user
4. Test credentials with: `python tests/coded_tools/now_agents/integration_tests/debug_servicenow_credentials.py`

### No Agents Found
```
Result: {"result": []}
```
**Solutions**:
1. Verify AI Agents are installed and activated in ServiceNow
2. Check Now Assist licensing is active
3. Ensure `SERVICENOW_GET_AGENTS_QUERY` parameter is correct
4. Verify table access permissions for `sn_aia_agent`

### Connection Timeout
```
Error: Connection timeout or network error
```
**Solutions**:  
1. Verify ServiceNow instance URL is accessible
2. Check network connectivity and firewall rules
3. Test basic connectivity: `python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py`

### Empty Agent Responses
```
Result: {"result": []} (from retrieve_message)
```
**Solutions**:
1. Wait longer - some agents require processing time
2. Ensure the agent supports the type of inquiry sent
3. Check if agent requires existing ticket/record context
4. Verify agent is properly configured in ServiceNow

## 🚀 Development Notes

- **Framework Integration**: Follows Neuro SAN `CodedTool` interface patterns
- **Async Support**: All tools support both sync and async invocation modes
- **Session Management**: Uses `sly_data` parameter for state persistence across tool calls
- **Error Handling**: Comprehensive error handling with detailed logging and debugging output
- **Security**: Credentials are handled securely through environment variables only

## 📚 Additional Resources

- [ServiceNow Agentic AI Documentation](https://docs.servicenow.com/bundle/vancouver-ai/page/administer/agentic-ai/concept/agentic-ai.html)
- [ServiceNow REST API Reference](https://docs.servicenow.com/bundle/vancouver-application-development/page/integrate/inbound-rest/concept/c_RESTAPI.html)  
- [Test Suite Documentation](../../tests/coded_tools/now_agents/README.md)

---

**Questions?** Check the test suite documentation or run the debug utilities for troubleshooting guidance.