import pytest
from unittest.mock import patch, MagicMock
from service_now import ServiceNowTool
from datetime import datetime, timezone

@pytest.fixture
def service_now_tool():
    with patch.dict('os.environ', {
        'SERVICENOW_INSTANCE': 'test.service-now.com',
        'SERVICENOW_USER': 'test_user',
        'SERVICENOW_PASSWORD': 'test_password'
    }):
        return ServiceNowTool()

@pytest.fixture
def mock_requests():
    with patch('service_now.requests') as mock_req:  # Changed from notification.requests to service_now.requests
        mock_response = MagicMock()
        mock_response.json.return_value = {'result': {'number': 'INC0001234'}}
        mock_req.post.return_value = mock_response
        yield mock_req

def test_create_ticket_success(service_now_tool, mock_requests):
    # Arrange
    test_data = {
        "recipient": "test.user@company.com",
        "notification_type": "temperature_alert",
        "title": "High Temperature Alert",
        "message": "Temperature exceeded threshold",
        "priority": "high",
        "action_required": True
    }

    # Act
    print("\nTesting create_ticket_success...")
    print(f"Test data: {test_data}")
    result = service_now_tool.create_ticket(**test_data)
    print(f"Result: {result}")

    # Assert
    assert result is True
    print("API call details:")
    print(f"URL called: {mock_requests.post.call_args[0][0]}")
    print(f"Request payload: {mock_requests.post.call_args[1]['json']}")
    mock_requests.post.assert_called_once()
    call_args = mock_requests.post.call_args
    assert call_args[0][0] == 'https://test.service-now.com/api/now/table/incident'
    assert call_args[1]['json']['short_description'] == "High Temperature Alert"
    assert call_args[1]['json']['priority'] == "2"  # high priority maps to 2

def test_create_ticket_failure(service_now_tool, mock_requests):
    # Arrange
    mock_requests.post.side_effect = Exception("Network error")
    test_data = {
        "recipient": "test.user@company.com",
        "notification_type": "pressure_alert",
        "title": "Low Pressure Alert",
        "message": "Pressure below threshold",
        "priority": "medium",
        "action_required": True
    }

    # Act
    result = service_now_tool.create_ticket(**test_data)

    # Assert
    assert result is False

def test_invoke_success(service_now_tool, mock_requests):
    # Arrange
    test_args = {
        "recipient": "test.user@company.com",
        "notification_type": "vibration_alert",
        "title": "High Vibration Alert",
        "message": "Vibration levels critical",
        "priority": "critical",
        "action_required": True
    }

    # Act
    print("\nTesting invoke_success...")
    print(f"Test args: {test_args}")
    result = service_now_tool.invoke(test_args, None)
    print(f"Invoke result: {result}")

    # Assert
    assert result['success'] is True
    assert result['recipient'] == test_args['recipient']
    assert result['notification_type'] == test_args['notification_type']
    assert result['priority'] == test_args['priority']
    assert 'timestamp' in result

def test_invoke_failure(service_now_tool, mock_requests):
    # Arrange
    mock_requests.post.side_effect = Exception("API error")
    test_args = {
        "recipient": "test.user@company.com",
        "notification_type": "humidity_alert",
        "title": "High Humidity Alert",
        "message": "Humidity exceeded threshold",
        "priority": "low",
        "action_required": True
    }

    # Act
    result = service_now_tool.invoke(test_args, None)

    # Assert
    assert 'error' in result
    assert result['recipient'] == test_args['recipient']
    assert 'timestamp' in result

def test_missing_required_args(service_now_tool):
    # Arrange
    test_args = {}  # Empty args

    # Act
    result = service_now_tool.invoke(test_args, None)

    # Assert
    assert 'error' in result
    assert 'timestamp' in result