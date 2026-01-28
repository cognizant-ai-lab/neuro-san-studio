#!/usr/bin/env python3
"""
Demo Workflow for Factory Sense New
Shows the complete Maestro orchestration workflow
"""

import json
import sys
import os
from datetime import datetime, timezone
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

class MaestroOrchestrator:
    """Maestro orchestrator that coordinates the workflow"""
    
    def __init__(self):
        self.sentinel = SentinelTool()
        self.medic = MedicTool()
        self.herald = HeraldTool()
        self.guardian = GuardianTool()
    
    def sage_decision_logic(self, metrics):
        """Sage decision logic - makes all decisions"""
        temperature = metrics.get("temperature", 0)
        humidity = metrics.get("humidity", 0)
        pressure = metrics.get("pressure", 0)
        vibration = metrics.get("vibration", 0)
        
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
        
        return {
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
    
    def orchestrate_workflow(self, machine_id="test-thing", mock_metrics=None):
        """Orchestrate the complete workflow"""
        print(f"\n{'='*80}")
        print(f"MAESTRO ORCHESTRATING WORKFLOW FOR MACHINE: {machine_id}")
        print(f"{'='*80}")
        
        workflow_results = {}
        
        # Step 1: Call Sentinel to get machine data
        print(f"\n1. SENTINEL - Monitoring machine {machine_id}")
        print("-" * 50)
        
        if mock_metrics:
            # Use mock data for demo
            structured_data = {
                "machine_id": machine_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": mock_metrics
            }
            print(f"✓ Mock data retrieved: {mock_metrics}")
        else:
            # Real AWS IoT call (would require certificates)
            sentinel_result = self.sentinel.invoke({"machine_id": machine_id}, {})
            if not sentinel_result.get("success"):
                print(f"❌ Sentinel failed: {sentinel_result.get('error')}")
                return None
            structured_data = sentinel_result.get("structured_data", {})
            print(f"✓ Data retrieved from AWS IoT")
        
        workflow_results["sentinel"] = structured_data
        
        # Step 2: Call Sage to make decisions
        print(f"\n2. SAGE - Making decisions based on data")
        print("-" * 50)
        
        metrics = structured_data.get("metrics", {})
        sage_decision = self.sage_decision_logic(metrics)
        
        print(f"✓ Severity: {sage_decision['severity']}")
        print(f"✓ Event Type: {sage_decision['event_type']}")
        print(f"✓ Manager Approval Required: {sage_decision['manager_approval_required']}")
        print(f"✓ Notification Required: {sage_decision['notification_required']}")
        
        workflow_results["sage"] = sage_decision
        
        # Step 3: Call Medic with Sage's recommendations
        print(f"\n3. MEDIC - Providing remedies")
        print("-" * 50)
        
        medic_args = {
            "machine_id": machine_id,
            "issue_type": sage_decision["event_type"],
            "severity": sage_decision["severity"],
            "current_metrics": metrics,
            "recommended_actions": [],
            "trend_analysis": {},
            "root_cause_analysis": {},
            "safety_considerations": sage_decision["safety_considerations"]
        }
        
        medic_result = self.medic.invoke(medic_args, {})
        if medic_result.get("success"):
            remedy = medic_result.get("remedy", {})
            print(f"✓ Remedies provided for {sage_decision['event_type']}")
            print(f"✓ Immediate Actions: {len(remedy.get('immediate_actions', []))} items")
            print(f"✓ Safety Precautions: {len(remedy.get('safety_precautions', []))} items")
        else:
            print(f"❌ Medic failed: {medic_result.get('error')}")
        
        workflow_results["medic"] = medic_result
        
        # Step 4: Call Herald with notification requirements
        print(f"\n4. HERALD - Sending notifications")
        print("-" * 50)
        
        if sage_decision.get("notification_required"):
            herald_args = {
                "recipient": sage_decision["recipient"],
                "notification_type": sage_decision["notification_type"],
                "title": f"{sage_decision['severity'].title()} Alert - {sage_decision['event_type']}",
                "message": f"Machine {machine_id} experiencing {sage_decision['event_type']}. Severity: {sage_decision['severity']}. Immediate attention required.",
                "priority": sage_decision["priority"],
                "channels": ["aws_iot"],
                "action_required": True
            }
            
            # For demo purposes, simulate notification instead of real AWS IoT call
            print(f"✓ [DEMO] Notification prepared for: {sage_decision['recipient']}")
            print(f"✓ [DEMO] Priority: {sage_decision['priority']}")
            print(f"✓ [DEMO] Type: {sage_decision['notification_type']}")
            print(f"✓ [DEMO] Title: {herald_args['title']}")
            print(f"✓ [DEMO] Message: {herald_args['message']}")
            herald_result = {"success": True, "demo_mode": True}
        else:
            print("✓ No notification required for normal operation")
            herald_result = {"success": True, "skipped": True}
        
        workflow_results["herald"] = herald_result
        
        # Step 5: Call Guardian if approval needed
        print(f"\n5. GUARDIAN - Handling approvals")
        print("-" * 50)
        
        if sage_decision.get("manager_approval_required"):
            guardian_args = {
                "action_description": f"Address {sage_decision['event_type']} on machine {machine_id}",
                "severity": sage_decision["severity"],
                "approver_role": "supervisor",
                "context_data": {
                    "machine_id": machine_id,
                    "event_type": sage_decision["event_type"],
                    "predicted_impact": sage_decision["predicted_impact"]
                },
                "approval_required_for": "safety_concern",
                "consequences_if_denied": "Safety risk may increase"
            }
            
            guardian_result = self.guardian.invoke(guardian_args, {})
            if guardian_result.get("success"):
                approval_result = guardian_result.get("approval_result", {})
                print(f"✓ Approval workflow: {approval_result.get('workflow_type')}")
                print(f"✓ Approval Status: {approval_result.get('approval_status')}")
                print(f"✓ Alert: {approval_result.get('alert_broadcast', 'N/A')[:50]}...")
            else:
                print(f"❌ Guardian failed: {guardian_result.get('error')}")
        else:
            print("✓ No approval required for normal operation")
            guardian_result = {"success": True, "skipped": True}
        
        workflow_results["guardian"] = guardian_result
        
        # Step 6: Provide final summary
        print(f"\n6. MAESTRO - Final Summary")
        print("-" * 50)
        
        print(f"✓ Workflow completed for machine: {machine_id}")
        print(f"✓ Severity Level: {sage_decision['severity']}")
        print(f"✓ Event Type: {sage_decision['event_type']}")
        print(f"✓ Actions Taken:")
        print(f"  - Data Monitoring: {'✓' if workflow_results['sentinel'] else '❌'}")
        print(f"  - Decision Making: {'✓' if workflow_results['sage'] else '❌'}")
        print(f"  - Remedy Provision: {'✓' if workflow_results['medic'].get('success') else '❌'}")
        print(f"  - Notification: {'✓' if workflow_results['herald'].get('success') else '❌'}")
        print(f"  - Approval: {'✓' if workflow_results['guardian'].get('success') else '❌'}")
        
        return workflow_results

def main():
    """Main demo function"""
    print("FACTORY SENSE NEW - WORKFLOW DEMO")
    print("="*80)
    print("Note: This demo uses mock data and simulated notifications")
    print("="*80)
    
    maestro = MaestroOrchestrator()
    
    # Demo scenarios
    demo_scenarios = [
        {
            "name": "Normal Operation",
            "machine_id": "machine-001",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 0.5}
        },
        {
            "name": "Temperature Warning",
            "machine_id": "machine-002",
            "metrics": {"temperature": 42.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 0.5}
        },
        {
            "name": "Humidity Critical",
            "machine_id": "machine-003",
            "metrics": {"temperature": 25.0, "humidity": 85.0, "pressure": 1013.25, "vibration": 0.5}
        },
        {
            "name": "Pressure Emergency",
            "machine_id": "machine-004",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1050.0, "vibration": 0.5}
        },
        {
            "name": "Vibration Critical",
            "machine_id": "machine-005",
            "metrics": {"temperature": 25.0, "humidity": 45.0, "pressure": 1013.25, "vibration": 6.0}
        }
    ]
    
    for scenario in demo_scenarios:
        print(f"\n{'='*80}")
        print(f"DEMO SCENARIO: {scenario['name']}")
        print(f"{'='*80}")
        
        result = maestro.orchestrate_workflow(
            machine_id=scenario["machine_id"],
            mock_metrics=scenario["metrics"]
        )
        
        if result:
            print(f"✅ Scenario completed successfully!")
        else:
            print(f"❌ Scenario failed!")
        
        # Add a pause between scenarios for better readability
        input("\nPress Enter to continue to next scenario...")
    
    print(f"\n{'='*80}")
    print("DEMO COMPLETED - ALL SCENARIOS TESTED")
    print(f"{'='*80}")

if __name__ == "__main__":
    main() 