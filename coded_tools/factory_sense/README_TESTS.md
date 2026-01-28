# Factory Sense New - Test Suite

This directory contains comprehensive tests for the Factory Sense New multi-agent system.

## Test Files

### 1. `test_factory_sense_new.py`
**Comprehensive Test Suite**
- Tests all components together in realistic scenarios
- Validates severity prediction accuracy
- Tests complete workflow orchestration
- Includes multiple test scenarios with different severity levels

**Usage:**
```bash
python test_factory_sense_new.py
```

### 2. `test_individual_components.py`
**Individual Component Tests**
- Tests each component (Sentinel, Sage, Medic, Herald, Guardian) in isolation
- Validates component-specific functionality
- Tests error handling and edge cases

**Usage:**
```bash
python test_individual_components.py
```

### 3. `demo_workflow.py`
**Workflow Demo**
- Demonstrates the complete Maestro orchestration workflow
- Shows real-time decision making and agent coordination
- Interactive demo with multiple scenarios
- Uses mock data for demonstration purposes

**Usage:**
```bash
python demo_workflow.py
```

### 4. `run_tests.py`
**Test Runner**
- Runs all test suites in sequence
- Provides comprehensive test results
- Exit codes for CI/CD integration

**Usage:**
```bash
python run_tests.py
```

## Test Scenarios

The test suite includes the following scenarios:

### Normal Operation
- Temperature: 25°C
- Humidity: 45%
- Pressure: 1013.25 hPa
- Vibration: 0.5
- Expected: Normal severity, no notifications

### Temperature Warning
- Temperature: 42°C (above 40°C threshold)
- Humidity: 45%
- Pressure: 1013.25 hPa
- Vibration: 0.5
- Expected: Warning severity, technician notification

### Humidity Critical
- Temperature: 25°C
- Humidity: 85% (above 80% threshold)
- Pressure: 1013.25 hPa
- Vibration: 0.5
- Expected: Critical severity, multi-level notification

### Pressure Emergency
- Temperature: 25°C
- Humidity: 45%
- Pressure: 1050.0 hPa (above 1040 hPa threshold)
- Vibration: 0.5
- Expected: Emergency severity, full escalation

### Vibration Critical
- Temperature: 25°C
- Humidity: 45%
- Pressure: 1013.25 hPa
- Vibration: 6.0 (above 5.0 threshold)
- Expected: Critical severity, maintenance notification

## Decision Thresholds

The system uses the following thresholds for decision making:

### Temperature
- Warning: ≥ 40°C
- Critical: ≥ 50°C
- Emergency: ≥ 60°C

### Humidity
- Warning: ≥ 70%
- Critical: ≥ 80%
- Emergency: ≥ 90%

### Pressure
- Warning: ≤ 1000 hPa OR ≥ 1020 hPa
- Critical: ≤ 990 hPa OR ≥ 1030 hPa
- Emergency: ≤ 980 hPa OR ≥ 1040 hPa

### Vibration
- Warning: ≥ 2.0
- Critical: ≥ 5.0
- Emergency: ≥ 8.0

## Notification Mapping

### Warning Severity
- Recipient: technician
- Priority: medium
- Type: warning

### Critical Severity
- Recipient: technician,supervisor,maintenance_manager
- Priority: high
- Type: alert

### Emergency Severity
- Recipient: technician,supervisor,maintenance_manager,emergency_response_team
- Priority: urgent
- Type: escalation

## Running Tests

### Run All Tests
```bash
python run_tests.py
```

### Run Individual Test Suites
```bash
# Comprehensive tests
python test_factory_sense_new.py

# Component tests
python test_individual_components.py

# Workflow demo
python demo_workflow.py
```

## Expected Output

All tests should show:
- ✅ for successful operations
- ❌ for failed operations
- Detailed logging of each step
- Summary of results at the end

## Dependencies

The tests require the following Python packages:
- `neuro_san` (for CodedTool interface)
- `awscrt` (for AWS IoT connectivity)
- `awsiot` (for MQTT operations)
- `python-dotenv` (for environment variables)

## Notes

- The tests use mock data for demonstration purposes
- Real AWS IoT connectivity requires proper certificates and configuration
- All tests are designed to run without external dependencies
- The demo workflow includes interactive pauses for better readability 