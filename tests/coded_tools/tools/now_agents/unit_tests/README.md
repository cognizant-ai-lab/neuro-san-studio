# Unit Tests - ServiceNow Agents

Fast, isolated tests using mocks. No external dependencies required.

## ✅ Status: All tests passing with 100% code coverage

## Files in this directory:

### `test_unit_agent_discovery_mocked.py`
**Tests**: `NowAgentAPIGetAgents` class  
**Purpose**: Validates agent discovery functionality with mocked ServiceNow API calls  
**Scenarios**:
- ✅ Successful agent discovery with valid response
- ✅ Authentication failures (401 errors) 
- ✅ Empty agent results handling
- ✅ Environment variable validation
- ✅ Async method delegation

### `test_unit_message_sending_mocked.py`
**Tests**: `NowAgentSendMessage` class  
**Purpose**: Validates message sending to ServiceNow agents with mocked API calls  
**Scenarios**:
- ✅ Successful message sending with session management
- ✅ Authentication failures (401 errors)
- ✅ Missing agent ID handling
- ✅ Environment variable validation
- ✅ Async method delegation

### `test_unit_message_retrieval_mocked.py`  
**Tests**: `NowAgentRetrieveMessage` class  
**Purpose**: Validates message retrieval with retry logic using mocked API calls  
**Scenarios**:
- ✅ Immediate response retrieval
- ✅ Response retrieval after retries (polling logic)
- ✅ Maximum retry attempts reached
- ✅ Missing session path handling
- ✅ Environment variable validation
- ✅ Async method delegation

## Quick Commands

```bash
# Run all unit tests
python -m pytest tests/coded_tools/now_agents/unit_tests/ -v

# Run with coverage report
python -m pytest tests/coded_tools/now_agents/unit_tests/ --cov=coded_tools.now_agents --cov-report=term-missing

# Run single test file
python -m pytest tests/coded_tools/now_agents/unit_tests/test_unit_agent_discovery_mocked.py -v
```

## Test Design Philosophy

These unit tests follow best practices:
- **Isolation**: Each test runs independently with fresh mocks
- **Fast**: All tests complete in < 1 second total
- **Comprehensive**: 100% code coverage with all edge cases
- **Maintainable**: Clear test names and good documentation
- **Reliable**: No external dependencies or network calls