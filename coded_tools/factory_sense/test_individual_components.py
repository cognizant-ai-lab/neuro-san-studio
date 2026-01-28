#!/usr/bin/env python3
"""
Individual Component Tests for Factory Sense New
Tests each component in isolation
"""

import json
import sys
import os
from datetime import datetime
import logging

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the tools
from sentinel.monitor import SentinelTool
from medic.remedy import MedicTool
from herald.notification import HeraldTool
from guardian.approval import GuardianTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_medic_tool():
    """Test Medic tool with various issue types"""
    print("\n" + "="*60)
    print("TESTING MEDIC TOOL - INDIVIDUAL COMPONENT")
    print("="*60)
    
    medic = MedicTool()
    
    test_cases = [
        {
            "name": "Temperature High Warning",
            "args": {
                "machine_id": "test-machine-001",
                "issue_type": "temperature_high",
                "severity": "warning",
                "current_metrics": {"temperature": 42.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 0.5}
            }
        },
        {
            "name": "Humidity Critical",
            "args": {
                "machine_id": "test-machine-002",
                "issue_type": "humidity_critical",
                "severity": "critical",
                "current_metrics": {"temperature": 25.0, "humidity": 85.0, "pressure": 1013.25, "vibration": 0.5}
            }
        },
        {
            "name": "Vibration Emergency",
            "args": {
                "machine_id": "test-machine-003",
                "issue_type": "vibration_excessive",
                "severity": "emergency",
                "current_metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 9.0}
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        result = medic.invoke(test_case['args'], {})
        
        if result.get("success"):
            remedy = result.get("remedy", {})
            print(f"✅ Success: {test_case['name']}")
            print(f"   Issue Type: {result['issue_type']}")
            print(f"   Severity: {result['severity']}")
            print(f"   Immediate Actions: {len(remedy.get('immediate_actions', []))}")
            print(f"   Safety Precautions: {len(remedy.get('safety_precautions', []))}")
            
            # Show first immediate action
            if remedy.get('immediate_actions'):
                print(f"   First Action: {remedy['immediate_actions'][0]}")
        else:
            print(f"❌ Failed: {test_case['name']} - {result.get('error')}")

def test_herald_tool():
    """Test Herald tool with various notification types"""
    print("\n" + "="*60)
    print("TESTING HERALD TOOL - INDIVIDUAL COMPONENT")
    print("="*60)
    
    herald = HeraldTool()
    
    test_cases = [
        {
            "name": "Warning Notification",
            "args": {
                "recipient": "technician",
                "notification_type": "warning",
                "title": "Temperature Warning",
                "message": "Machine temperature is above normal threshold",
                "priority": "medium",
                "action_required": True
            }
        },
        {
            "name": "Critical Alert",
            "args": {
                "recipient": "technician,supervisor,maintenance_manager",
                "notification_type": "alert",
                "title": "Critical Humidity Alert",
                "message": "Machine humidity is at critical levels",
                "priority": "high",
                "action_required": True
            }
        },
        {
            "name": "Emergency Escalation",
            "args": {
                "recipient": "technician,supervisor,maintenance_manager,emergency_response_team",
                "notification_type": "escalation",
                "title": "Emergency Pressure Alert",
                "message": "Machine pressure is at emergency levels",
                "priority": "urgent",
                "action_required": True
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        result = herald.invoke(test_case['args'], {})
        
        if result.get("success"):
            print(f"✅ Success: {test_case['name']}")
            print(f"   Recipient: {result['recipient']}")
            print(f"   Notification Type: {result['notification_type']}")
            print(f"   Priority: {result['priority']}")
        else:
            print(f"❌ Failed: {test_case['name']} - {result.get('error')}")

def test_guardian_tool():
    """Test Guardian tool with various approval scenarios"""
    print("\n" + "="*60)
    print("TESTING GUARDIAN TOOL - INDIVIDUAL COMPONENT")
    print("="*60)
    
    guardian = GuardianTool()
    
    test_cases = [
        {
            "name": "Warning Approval Required",
            "args": {
                "action_description": "Adjust temperature settings on machine test-001",
                "severity": "warning",
                "approver_role": "supervisor",
                "context_data": {"machine_id": "test-001", "temperature": 42.0},
                "approval_required_for": "parameter_adjustment",
                "consequences_if_denied": "Temperature may continue to rise"
            }
        },
        {
            "name": "Critical Auto-Approval",
            "args": {
                "action_description": "Emergency shutdown of machine test-002",
                "severity": "critical",
                "approver_role": "manager",
                "context_data": {"machine_id": "test-002", "humidity": 85.0},
                "approval_required_for": "safety_concern",
                "consequences_if_denied": "Equipment damage risk"
            }
        },
        {
            "name": "Emergency Auto-Approval",
            "args": {
                "action_description": "Immediate safety intervention on machine test-003",
                "severity": "emergency",
                "approver_role": "emergency_team",
                "context_data": {"machine_id": "test-003", "pressure": 1050.0},
                "approval_required_for": "safety_emergency",
                "consequences_if_denied": "Safety hazard"
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        result = guardian.invoke(test_case['args'], {})
        
        if result.get("success"):
            approval_result = result.get("approval_result", {})
            print(f"✅ Success: {test_case['name']}")
            print(f"   Workflow Type: {approval_result.get('workflow_type')}")
            print(f"   Approval Required: {approval_result.get('approval_required')}")
            print(f"   Approval Status: {approval_result.get('approval_status')}")
            print(f"   Alert: {approval_result.get('alert_broadcast', 'N/A')[:50]}...")
        else:
            print(f"❌ Failed: {test_case['name']} - {result.get('error')}")

def test_sage_decision_logic():
    """Test Sage decision logic with various metric combinations"""
    print("\n" + "="*60)
    print("TESTING SAGE DECISION LOGIC - INDIVIDUAL COMPONENT")
    print("="*60)
    
    test_cases = [
        {
            "name": "Normal Operation",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 0.5},
            "expected_severity": "normal"
        },
        {
            "name": "Temperature Warning",
            "metrics": {"temperature": 42.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 0.5},
            "expected_severity": "warning"
        },
        {
            "name": "Humidity Critical",
            "metrics": {"temperature": 25.0, "humidity": 85.0, "pressure": 1013.25, "vibration": 0.5},
            "expected_severity": "critical"
        },
        {
            "name": "Pressure Emergency",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1050.0, "vibration": 0.5},
            "expected_severity": "emergency"
        },
        {
            "name": "Vibration Critical",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 6.0},
            "expected_severity": "critical"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        
        metrics = test_case["metrics"]
        temperature = metrics["temperature"]
        humidity = metrics["humidity"]
        pressure = metrics["pressure"]
        vibration = metrics["vibration"]
        
        print(f"   Metrics: T={temperature}°C, H={humidity}%, P={pressure}hPa, V={vibration}")
        
        # Apply decision logic
        severity = "normal"
        event_type = "normal_operation"
        
        # Check emergency thresholds
        if (temperature >= 60 or humidity >= 90 or 
            pressure <= 980 or pressure >= 1040 or vibration >= 8.0):
            severity = "emergency"
            if temperature >= 60:
                event_type = "temperature_emergency"
            elif humidity >= 90:
                event_type = "humidity_emergency"
            elif pressure <= 980 or pressure >= 1040:
                event_type = "pressure_emergency"
            elif vibration >= 8.0:
                event_type = "vibration_emergency"
        
        # Check critical thresholds
        elif (temperature >= 50 or humidity >= 80 or 
              pressure <= 990 or pressure >= 1030 or vibration >= 5.0):
            severity = "critical"
            if temperature >= 50:
                event_type = "temperature_critical"
            elif humidity >= 80:
                event_type = "humidity_critical"
            elif pressure <= 990 or pressure >= 1030:
                event_type = "pressure_critical"
            elif vibration >= 5.0:
                event_type = "vibration_critical"
        
        # Check warning thresholds
        elif (temperature >= 40 or humidity >= 70 or 
              pressure <= 1000 or pressure >= 1020 or vibration >= 2.0):
            severity = "warning"
            if temperature >= 40:
                event_type = "temperature_warning"
            elif humidity >= 70:
                event_type = "humidity_warning"
            elif pressure <= 1000 or pressure >= 1020:
                event_type = "pressure_warning"
            elif vibration >= 2.0:
                event_type = "vibration_warning"
        
        # Check if prediction is correct
        correct = severity == test_case["expected_severity"]
        status = "✅" if correct else "❌"
        
        print(f"   {status} Expected: {test_case['expected_severity']}, Got: {severity}")
        print(f"   Event Type: {event_type}")

def main():
    """Run all individual component tests"""
    print("FACTORY SENSE NEW - INDIVIDUAL COMPONENT TESTS")
    print("="*80)
    print(f"Test started at: {datetime.now().isoformat()}")
    
    try:
        # Test Sage decision logic
        test_sage_decision_logic()
        
        # Test Medic tool
        test_medic_tool()
        
        # Test Herald tool
        test_herald_tool()
        
        # Test Guardian tool
        test_guardian_tool()
        
        print(f"\n{'='*80}")
        print("ALL INDIVIDUAL COMPONENT TESTS COMPLETED")
        print(f"Test completed at: {datetime.now().isoformat()}")
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 