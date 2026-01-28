import pytest
import os
from dotenv import load_dotenv
from service_now import ServiceNowTool
from datetime import datetime, timezone

# Load environment variables from .env file
load_dotenv()

@pytest.fixture
def service_now_tool():
    return ServiceNowTool()

def test_create_real_ticket(service_now_tool):
    # Arrange
    test_data = {
        "recipient": "IoT_Test@cognizant.com",
        "notification_type": "test_alert",
        "title": "Test Ticket - Please Ignore",
        "message": f"Integration test ticket created at {datetime.now(timezone.utc)}",
        "priority": "low",
        "action_required": False
    }

    # Act
    print("\nCreating real ServiceNow ticket...")
    print(f"Test data: {test_data}")
    print(f"Using ServiceNow instance: {service_now_tool.instance}")
    result = service_now_tool.create_ticket(**test_data)
    print(f"Result: {result}")

    # Assert
    assert result is True, "Failed to create ServiceNow ticket. Check credentials and network connection."

def test_real_invoke(service_now_tool):
    # Arrange
    test_args = {
        "recipient": "your.email@cognizant.com",
        "notification_type": "test_notification",
        "title": "Test Notification - Please Ignore",
        "message": f"Integration test notification at {datetime.now(timezone.utc)}",
        "priority": "low",
        "action_required": False
    }

    # Act
    print("\nTesting real invoke...")
    print(f"Test args: {test_args}")
    result = service_now_tool.invoke(test_args, None)
    print(f"Invoke result: {result}")

    # Assert
    assert result['success'] is True