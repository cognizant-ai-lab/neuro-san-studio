#!/usr/bin/env python3
"""
Test Program for Factory Sense New Multi-Agent System
Tests all components: Sentinel, Sage, Medic, Herald, and Guardian
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FactorySenseNewTester:
    """Test class for Factory Sense New system"""
    
    def __init__(self):
        self.sentinel = SentinelTool()
        self.medic = MedicTool()
        self.herald = HeraldTool()
        self.guardian = GuardianTool()
        
        # Test data based on your payload structure
        self.test_payload = {
            "state": {
                "desired": {
                    "welcome": "aws-iot"
                },
                "reported": {
                    "welcome": "aws-iot",
                    "timestamp": "2025-09-19T09:21:40.652929Z",
                    "temperature": 36.45,
                    "humidity": 58.49,
                    "pressure": 1009.72,
                    "acceleration": {
                        "x": 0.0033942428417503834,
                        "y": 0.020151784643530846,
                        "z": 0.9772243499755859
                    },
                    "vibration": 0.977,
                    "orientation": {
                        "pitch": 3.12,
                        "roll": 221.95,
                        "yaw": 279.63
                    },
                    "magnetic_field": {
                        "x": -13.67,
                        "y": -1.29,
                        "z": -13.63
                    }
                }
            }
        }
        
        # Test scenarios with different severity levels
        self.test_scenarios = [
            {
                "name": "Normal Operation",
                "temperature": 25.0,
                "humidity": 45.0,
                "pressure": 1013.25,
                "vibration": 0.5,
                "expected_severity": "normal"
            },
            {
                "name": "Temperature Warning",
                "temperature": 42.0,
                "humidity": 45.0,
                "pressure": 1013.25,
                "vibration": 0.5,
                "expected_severity": "warning"
            },
            {
                "name": "Humidity Critical",
                "temperature": 25.0,
                "humidity": 85.0,
                "pressure": 1013.25,
                "vibration": 0.5,
                "expected_severity": "critical"
            },
            {
                "name": "Pressure Emergency",
                "temperature": 25.0,
                "humidity": 45.0,
                "pressure": 1050.0,
                "vibration": 0.5,
                "expected_severity": "emergency"
            },
            {
                "name": "Vibration Critical",
                "temperature": 25.0,
                "humidity": 45.0,
                "pressure": 1013.25,
                "vibration": 6.0,
                "expected_severity": "critical"
            }
        ]
    
    def test_sentinel_tool(self):
        """Test the Sentinel tool with mock data"""
        print("\n" + "="*60)
        print("TESTING SENTINEL TOOL")
        print("="*60)
        
        # Mock the AWS IoT connection for testing
        print("Note: This test uses mock data since AWS IoT connection requires certificates")
        
        # Simulate the sentinel processing
        reported = self.test_payload["state"]["reported"]
        
        # Extract only the required metrics
        metrics = {
            "temperature": reported.get("temperature"),
            "humidity": reported.get("humidity"),
            "pressure": reported.get("pressure"),
            "vibration": reported.get("vibration")
        }
        
        structured_data = {
            "machine_id": "test-thing",
            "timestamp": reported.get("timestamp", datetime.utcnow().isoformat()),
            "metrics": metrics
        }
        
        print(f"✓ Extracted metrics: {metrics}")
        print(f"✓ Structured data: {json.dumps(structured_data, indent=2)}")
        
        return {
            "shadow_document": self.test_payload,
            "structured_data": structured_data,
            "success": True
        }
    
    def test_sage_decision_logic(self, metrics):
        """Test the Sage decision logic"""
        print("\n" + "="*60)
        print("TESTING SAGE DECISION LOGIC")
        print("="*60)
        
        temperature = metrics.get("temperature", 0)
        humidity = metrics.get("humidity", 0)
        pressure = metrics.get("pressure", 0)
        vibration = metrics.get("vibration", 0)
        
        print(f"Analyzing metrics: T={temperature}°C, H={humidity}%, P={pressure}hPa, V={vibration}")
        
        # Apply decision thresholds
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
        
        # Determine notification requirements
        if severity == "normal":
            notification_required = False
            recipient = None
            priority = None
            notification_type = None
        elif severity == "warning":
            notification_required = True
            recipient = "technician"
            priority = "medium"
            notification_type = "warning"
        elif severity == "critical":
            notification_required = True
            recipient = "technician,supervisor,maintenance_manager"
            priority = "high"
            notification_type = "alert"
        elif severity == "emergency":
            notification_required = True
            recipient = "technician,supervisor,maintenance_manager,emergency_response_team"
            priority = "urgent"
            notification_type = "escalation"
        
        sage_decision = {
            "severity": severity,
            "event_type": event_type,
            "manager_approval_required": severity in ["warning", "critical", "emergency"],
            "notification_required": notification_required,
            "recipient": recipient,
            "priority": priority,
            "notification_type": notification_type,
            "predicted_impact": f"{severity.title()} level impact on operations",
            "safety_considerations": [
                "Monitor situation closely",
                "Ensure personnel safety",
                "Document all actions"
            ]
        }
        
        print(f"✓ Severity: {severity}")
        print(f"✓ Event Type: {event_type}")
        print(f"✓ Manager Approval Required: {sage_decision['manager_approval_required']}")
        print(f"✓ Notification Required: {notification_required}")
        if notification_required:
            print(f"✓ Recipient: {recipient}")
            print(f"✓ Priority: {priority}")
            print(f"✓ Notification Type: {notification_type}")
        
        return sage_decision
    
    def test_medic_tool(self, sage_decision, metrics):
        """Test the Medic tool"""
        print("\n" + "="*60)
        print("TESTING MEDIC TOOL")
        print("="*60)
        
        args = {
            "machine_id": "test-thing",
            "issue_type": sage_decision["event_type"],
            "severity": sage_decision["severity"],
            "current_metrics": metrics,
            "recommended_actions": [],
            "trend_analysis": {},
            "root_cause_analysis": {},
            "safety_considerations": sage_decision["safety_considerations"]
        }
        
        result = self.medic.invoke(args, {})
        
        if result.get("success"):
            remedy = result.get("remedy", {})
            print(f"✓ Issue Type: {result['issue_type']}")
            print(f"✓ Severity: {result['severity']}")
            print(f"✓ Immediate Actions: {len(remedy.get('immediate_actions', []))} items")
            print(f"✓ Short-term Solutions: {len(remedy.get('short_term_solutions', []))} items")
            print(f"✓ Long-term Prevention: {len(remedy.get('long_term_prevention', []))} items")
            print(f"✓ Safety Precautions: {len(remedy.get('safety_precautions', []))} items")
            
            # Show first few immediate actions
            if remedy.get('immediate_actions'):
                print("  First immediate action:", remedy['immediate_actions'][0])
        else:
            print(f"❌ Medic test failed: {result.get('error')}")
        
        return result
    
    def test_herald_tool(self, sage_decision):
        """Test the Herald tool"""
        print("\n" + "="*60)
        print("TESTING HERALD TOOL")
        print("="*60)
        
        if not sage_decision.get("notification_required"):
            print("✓ No notification required for normal operation")
            return {"success": True, "skipped": True}
        
        args = {
            "recipient": sage_decision["recipient"],
            "notification_type": sage_decision["notification_type"],
            "title": f"{sage_decision['severity'].title()} Alert - {sage_decision['event_type']}",
            "message": f"Machine test-thing experiencing {sage_decision['event_type']}. Severity: {sage_decision['severity']}. Immediate attention required.",
            "priority": sage_decision["priority"],
            "channels": ["aws_iot"],
            "action_required": True
        }
        
        print(f"✓ Preparing notification for: {args['recipient']}")
        print(f"✓ Notification type: {args['notification_type']}")
        print(f"✓ Priority: {args['priority']}")
        print(f"✓ Title: {args['title']}")
        print(f"✓ Message: {args['message']}")
        
        # Note: This would normally send via AWS IoT, but we're just testing the logic
        print("✓ Notification prepared (AWS IoT sending simulated)")
        
        return {"success": True, "notification_prepared": True}
    
    def test_guardian_tool(self, sage_decision):
        """Test the Guardian tool"""
        print("\n" + "="*60)
        print("TESTING GUARDIAN TOOL")
        print("="*60)
        
        if not sage_decision.get("manager_approval_required"):
            print("✓ No approval required for normal operation")
            return {"success": True, "skipped": True}
        
        args = {
            "action_description": f"Address {sage_decision['event_type']} on machine test-thing",
            "severity": sage_decision["severity"],
            "approver_role": "supervisor",
            "context_data": {
                "machine_id": "test-thing",
                "event_type": sage_decision["event_type"],
                "predicted_impact": sage_decision["predicted_impact"]
            },
            "approval_required_for": "safety_concern",
            "consequences_if_denied": "Safety risk may increase"
        }
        
        result = self.guardian.invoke(args, {})
        
        if result.get("success"):
            approval_result = result.get("approval_result", {})
            print(f"✓ Workflow Type: {approval_result.get('workflow_type')}")
            print(f"✓ Alert Broadcast: {approval_result.get('alert_broadcast')}")
            print(f"✓ Approval Required: {approval_result.get('approval_required')}")
            print(f"✓ Approval Status: {approval_result.get('approval_status')}")
        else:
            print(f"❌ Guardian test failed: {result.get('error')}")
        
        return result
    
    def run_test_scenario(self, scenario):
        """Run a complete test scenario"""
        print(f"\n{'='*80}")
        print(f"TESTING SCENARIO: {scenario['name']}")
        print(f"Expected Severity: {scenario['expected_severity']}")
        print(f"{'='*80}")
        
        # Create metrics for this scenario
        metrics = {
            "temperature": scenario["temperature"],
            "humidity": scenario["humidity"],
            "pressure": scenario["pressure"],
            "vibration": scenario["vibration"]
        }
        
        # Test Sentinel (mock)
        sentinel_result = self.test_sentinel_tool()
        
        # Test Sage decision logic
        sage_decision = self.test_sage_decision_logic(metrics)
        
        # Verify expected severity
        if sage_decision["severity"] == scenario["expected_severity"]:
            print(f"✅ Severity prediction CORRECT: {sage_decision['severity']}")
        else:
            print(f"❌ Severity prediction INCORRECT: Expected {scenario['expected_severity']}, got {sage_decision['severity']}")
        
        # Test Medic
        medic_result = self.test_medic_tool(sage_decision, metrics)
        
        # Test Herald
        herald_result = self.test_herald_tool(sage_decision)
        
        # Test Guardian
        guardian_result = self.test_guardian_tool(sage_decision)
        
        return {
            "scenario": scenario["name"],
            "expected_severity": scenario["expected_severity"],
            "actual_severity": sage_decision["severity"],
            "correct_prediction": sage_decision["severity"] == scenario["expected_severity"],
            "sentinel_success": sentinel_result.get("success", False),
            "medic_success": medic_result.get("success", False),
            "herald_success": herald_result.get("success", False),
            "guardian_success": guardian_result.get("success", False)
        }
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("FACTORY SENSE NEW - COMPREHENSIVE TEST SUITE")
        print("="*80)
        print(f"Test started at: {datetime.now().isoformat()}")
        
        results = []
        
        # Run each test scenario
        for scenario in self.test_scenarios:
            result = self.run_test_scenario(scenario)
            results.append(result)
        
        # Print summary
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        
        total_tests = len(results)
        correct_predictions = sum(1 for r in results if r["correct_prediction"])
        
        print(f"Total Scenarios Tested: {total_tests}")
        print(f"Correct Severity Predictions: {correct_predictions}/{total_tests}")
        print(f"Accuracy: {(correct_predictions/total_tests)*100:.1f}%")
        
        print(f"\nDetailed Results:")
        for result in results:
            status = "✅" if result["correct_prediction"] else "❌"
            print(f"  {status} {result['scenario']}: {result['expected_severity']} → {result['actual_severity']}")
        
        # Test individual components
        print(f"\nComponent Tests:")
        print(f"  Sentinel: {'✅' if all(r['sentinel_success'] for r in results) else '❌'}")
        print(f"  Medic: {'✅' if all(r['medic_success'] for r in results) else '❌'}")
        print(f"  Herald: {'✅' if all(r['herald_success'] for r in results) else '❌'}")
        print(f"  Guardian: {'✅' if all(r['guardian_success'] for r in results) else '❌'}")
        
        print(f"\nTest completed at: {datetime.now().isoformat()}")
        
        return results

def main():
    """Main test function"""
    try:
        tester = FactorySenseNewTester()
        results = tester.run_all_tests()
        
        # Return exit code based on results
        all_correct = all(r["correct_prediction"] for r in results)
        return 0 if all_correct else 1
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 