# ServiceNow Agents Test Suite

Complete test suite for ServiceNow AI agents integration with clear separation between unit and integration tests.

## 📁 Directory Structure

```
tests/coded_tools/now_agents/
├── unit_tests/                              # Fast, isolated, mocked tests
│   ├── test_unit_agent_discovery_mocked.py     # Agent discovery with API mocks
│   ├── test_unit_message_sending_mocked.py     # Message sending with API mocks
│   └── test_unit_message_retrieval_mocked.py   # Message retrieval with API mocks
├── integration_tests/                       # Real API tests (require credentials)
│   ├── test_integration_servicenow_connectivity.py      # Basic ServiceNow connectivity
│   ├── test_integration_agent_discovery_simple.py      # Simple agent discovery
│   ├── test_integration_agent_discovery_debug.py       # Agent discovery with debug output
│   ├── test_integration_full_workflow_e2e.py           # End-to-end workflow test
│   └── debug_servicenow_credentials.py                 # Credential validation utility
└── README.md                                # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Testing dependencies installed:
  - `pip install pytest pytest-cov` (individual packages)
  - OR `pip install -r build-requirements.txt` (all build dependencies - recommended)
- For integration tests: Valid ServiceNow credentials in `.env` file

### Run All Tests
```bash
# From project root - Run all unit tests (fast, no credentials needed)
python -m pytest tests/coded_tools/now_agents/unit_tests/ -v

# Run all integration tests (requires ServiceNow credentials)
python -m pytest tests/coded_tools/now_agents/integration_tests/ -v
```

## 🧪 Unit Tests (Mocked)

**Purpose**: Test business logic and error handling without external dependencies
**Speed**: Fast (< 1 second total)
**Requirements**: None (fully mocked)
**Coverage**: 100% code coverage achieved ✅

### Individual Unit Tests
```bash
# Test agent discovery functionality (mocked API calls)
python -m pytest tests/coded_tools/now_agents/unit_tests/test_unit_agent_discovery_mocked.py -v

# Test message sending functionality (mocked API calls)
python -m pytest tests/coded_tools/now_agents/unit_tests/test_unit_message_sending_mocked.py -v

# Test message retrieval with retry logic (mocked API calls)
python -m pytest tests/coded_tools/now_agents/unit_tests/test_unit_message_retrieval_mocked.py -v
```

### Unit Test Coverage Report
```bash
# Generate detailed coverage report
python -m pytest tests/coded_tools/now_agents/unit_tests/ --cov=coded_tools.now_agents --cov-report=html
# Open htmlcov/index.html for detailed report
```

### What Unit Tests Cover
- ✅ Successful API responses and data parsing
- ✅ Authentication failures (401, 403 errors)
- ✅ Network errors and timeouts
- ✅ Empty/invalid API responses
- ✅ Environment variable handling
- ✅ Session management and data persistence
- ✅ Async method delegation
- ✅ Retry logic and polling behavior

## 🌐 Integration Tests (Real API)

**Purpose**: Test real ServiceNow API interactions and end-to-end workflows
**Speed**: Slower (network dependent)
**Requirements**: Valid ServiceNow credentials and permissions
**Status**: ✅ Working! Successfully discovering 100+ ServiceNow AI agents

### Setup Integration Tests

#### 1. Environment Configuration
Create `.env` file in project root:
```bash
# Required ServiceNow Configuration
SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
SERVICENOW_USER="your-username"
SERVICENOW_PWD="your-password"
SERVICENOW_CALLER_EMAIL="your-email@company.com"
SERVICENOW_GET_AGENTS_QUERY="active=true"
```

#### 2. ServiceNow Permissions Required
The ServiceNow user needs access to:
- `sn_aia_agent` table (AI Agent definitions)
- `sn_aia_external_agent_execution` table (Message interactions)
- Agentic AI API endpoints (`/api/sn_aia/agenticai/v1/`)

### Individual Integration Tests

```bash
# Test basic ServiceNow instance connectivity (no auth needed)
python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py

# Validate ServiceNow credentials and permissions
python tests/coded_tools/now_agents/integration_tests/debug_servicenow_credentials.py

# Simple agent discovery test with minimal output
python tests/coded_tools/now_agents/integration_tests/test_integration_agent_discovery_simple.py

# Agent discovery with detailed debug information
python tests/coded_tools/now_agents/integration_tests/test_integration_agent_discovery_debug.py

# Full end-to-end workflow: discover → send message → retrieve response
python tests/coded_tools/now_agents/integration_tests/test_integration_full_workflow_e2e.py
```

### What Integration Tests Cover
- 🔌 Real ServiceNow instance connectivity
- 🔐 Authentication and authorization
- 🤖 Actual AI agent discovery
- 📤 Real message sending to agents
- 📥 Response retrieval from agents
- 🔄 End-to-end workflow validation
- ⏱️ Real network timeouts and retry behavior

## 🐛 Common Issues & Solutions

### Integration Test Permission Errors
If you encounter **403 Forbidden** errors when running integration tests:

**Error**: `Status: 403, Headers: {...}`
```json
{
  "error": {
    "message": "Insufficient rights to query records",
    "detail": "Field(s) present in the query do not have permission to be read"
  },
  "status": "failure"
}
```

**Root Cause**: Your ServiceNow user lacks permissions to access AI Agent tables.

**Solution Steps**:
1. **Contact your ServiceNow administrator** to grant the following permissions:
   - `sn_aia_agent.read` - Read AI agent definitions
   - `sn_aia_external_agent_execution.read` - Read agent interactions
   - `sn_aia_external_agent_execution.create` - Send messages to agents
   - Access to Agentic AI API endpoints (`/api/sn_aia/agenticai/v1/`)

2. **Test credentials** using: `python tests/coded_tools/now_agents/integration_tests/debug_servicenow_credentials.py`

3. **Verify basic connectivity** first: `python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py`

**Note**: The current test credentials have been configured with proper permissions and work successfully.

### ServiceNow Agent Limitations
- Most AI agents require existing tickets/records to function properly
- Single interaction mode only (multi-turn conversations not yet supported)
- Some agents may not respond immediately (async processing)

## 📊 Test Results Status

| Test Category | Status | Coverage | Details |
|---------------|--------|----------|---------|
| **Unit Tests** | ✅ PASSING | 100% | All 15 tests pass with full code coverage |
| **Integration Tests** | ✅ PASSING | N/A | Successfully discovering 100+ ServiceNow AI agents |

## 🔧 Troubleshooting

### Unit Test Issues
```bash
# If unit tests fail, check imports and paths
python -c "from coded_tools.now_agents.nowagent_api_get_agents import NowAgentAPIGetAgents; print('Imports OK')"

# Run with verbose output for debugging
python -m pytest tests/coded_tools/now_agents/unit_tests/ -v -s
```

### Integration Test Issues
```bash
# Test basic connectivity first
python tests/coded_tools/now_agents/integration_tests/test_integration_servicenow_connectivity.py

# Check credentials
python tests/coded_tools/now_agents/integration_tests/debug_servicenow_credentials.py

# Verify .env file exists and has required variables
ls .env && grep -E "SERVICENOW_(INSTANCE_URL|USER|PWD)" .env
```

### Common Fixes
1. **Import Errors**: Ensure you're running from project root directory
2. **403 Forbidden**: Contact ServiceNow admin for permissions
3. **Connection Timeouts**: Check ServiceNow instance URL and network connectivity
4. **Missing .env**: Create `.env` file with required ServiceNow configuration

## 🚀 Development Workflow

### Adding New Tests
1. **Unit Tests**: Add to `unit_tests/` directory with `test_unit_*` prefix
2. **Integration Tests**: Add to `integration_tests/` directory with `test_integration_*` prefix
3. **Follow naming convention**: `test_{type}_{functionality}_{description}.py`

### Before Committing
```bash
# Ensure all unit tests pass with full coverage
python -m pytest tests/coded_tools/now_agents/unit_tests/ --cov=coded_tools.now_agents --cov-fail-under=100

# Test integration tests if ServiceNow access available
python -m pytest tests/coded_tools/now_agents/integration_tests/ -v
```

### CI/CD Integration
```yaml
# Example GitHub Actions configuration
- name: Run Unit Tests
  run: python -m pytest tests/coded_tools/now_agents/unit_tests/ --cov=coded_tools.now_agents --cov-fail-under=100

- name: Run Integration Tests
  run: python -m pytest tests/coded_tools/now_agents/integration_tests/ -v
  env:
    SERVICENOW_INSTANCE_URL: ${{ secrets.SERVICENOW_INSTANCE_URL }}
    SERVICENOW_USER: ${{ secrets.SERVICENOW_USER }}
    SERVICENOW_PWD: ${{ secrets.SERVICENOW_PWD }}
    SERVICENOW_CALLER_EMAIL: ${{ secrets.SERVICENOW_CALLER_EMAIL }}
    SERVICENOW_GET_AGENTS_QUERY: "active=true"
```

## 📚 Additional Resources

- [ServiceNow Agentic AI Documentation](https://www.servicenow.com/docs/bundle/yokohama-intelligent-experiences/page/administer/now-assist-ai-agents/concept/exploring-ai-agents.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Python Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

---

**Need Help?** Check the troubleshooting section above or contact the development team.