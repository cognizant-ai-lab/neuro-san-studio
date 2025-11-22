# Integration Tests - ServiceNow Agents

Real API tests that validate actual ServiceNow connectivity and workflows.

## ✅ Status: Working! Successfully discovering 100+ ServiceNow AI agents

## Files in this directory:

### `test_integration_servicenow_connectivity.py`
**Purpose**: Tests basic ServiceNow instance accessibility  
**Requirements**: None (no authentication needed)  
**What it tests**:
- ✅ ServiceNow instance is accessible
- ✅ Login page responds correctly
- ✅ API endpoints return expected authentication requirements

**Run**: `python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py`

### `debug_servicenow_credentials.py`  
**Purpose**: Validates ServiceNow credentials and permissions  
**Requirements**: ServiceNow credentials in `.env`  
**What it tests**:
- Environment variable presence
- Basic authentication against ServiceNow
- Permission to access required tables
- Detailed error reporting for troubleshooting

**Run**: `python tests/coded_tools/now_agents/integration_tests/debug_servicenow_credentials.py`

### `test_integration_agent_discovery_simple.py`
**Purpose**: Simple test of ServiceNow agent discovery  
**Requirements**: ServiceNow credentials + permissions  
**What it tests**:
- Real API call to discover ServiceNow AI agents
- Basic connectivity and authentication
- Agent data parsing and validation

**Run**: `python tests/coded_tools/now_agents/integration_tests/test_integration_agent_discovery_simple.py`

### `test_integration_agent_discovery_debug.py`
**Purpose**: Agent discovery with detailed debug output  
**Requirements**: ServiceNow credentials + permissions  
**What it tests**:
- Same as simple test but with verbose debugging
- Environment variable troubleshooting
- Detailed error reporting and stack traces

**Run**: `python tests/coded_tools/now_agents/integration_tests/test_integration_agent_discovery_debug.py`

### `test_integration_full_workflow_e2e.py`
**Purpose**: Complete end-to-end workflow test  
**Requirements**: ServiceNow credentials + full permissions  
**What it tests**:
- Agent discovery → Message sending → Response retrieval
- Session management across multiple API calls  
- Real timeout and retry behavior
- Complete integration validation

**Run**: `python tests/coded_tools/now_agents/integration_tests/test_integration_full_workflow_e2e.py`

## Setup Requirements

### 1. Environment File (.env)
Create in project root with:
```bash
SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
SERVICENOW_USER="your-username" 
SERVICENOW_PWD="your-password"
SERVICENOW_CALLER_EMAIL="your-email@company.com"
SERVICENOW_GET_AGENTS_QUERY="active=true"
```

### 2. ServiceNow Permissions
Contact your ServiceNow administrator to grant:
- `sn_aia_agent.read` - Read AI agent definitions
- `sn_aia_external_agent_execution.read` - Read agent interactions  
- `sn_aia_external_agent_execution.create` - Send messages to agents
- Access to Agentic AI API endpoints

## Potential Issue: 403 Forbidden Error

If you encounter **403 Forbidden** errors with different ServiceNow credentials:

**Error Message**:
```json
{
  "error": {
    "message": "Insufficient rights to query records",
    "detail": "Field(s) present in the query do not have permission to be read"
  },
  "status": "failure"
}
```

**Root Cause**: ServiceNow user lacks permissions to access `sn_aia_agent` table

**Solution**: Contact ServiceNow admin to grant appropriate AI Agent roles/permissions

**Note**: The current test environment (`neuro.ai` user) has been properly configured and works successfully.

## Recommended Test Order

1. **Start here**: `test_integration_servicenow_connectivity.py` (no credentials needed)
2. **Check setup**: `debug_servicenow_credentials.py` (validates credentials)  
3. **Simple test**: `test_integration_agent_discovery_simple.py` (basic functionality)
4. **Debug issues**: `test_integration_agent_discovery_debug.py` (detailed output)
5. **Full validation**: `test_integration_full_workflow_e2e.py` (complete workflow)

## Expected Behavior When Fixed

When ServiceNow permissions are resolved, these tests should:
- ✅ Discover 50+ ServiceNow AI agents
- ✅ Successfully send messages to agents  
- ✅ Retrieve responses (may be empty for some agents)
- ✅ Validate complete end-to-end workflow

## Limitations

- Most ServiceNow AI agents require existing tickets/records
- Single interaction mode (no multi-turn conversations)
- Some agents may not respond immediately due to async processing
- Network timeouts may occur with slow ServiceNow instances