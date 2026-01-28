# factory_sense_new/guardian/approval.py
from neuro_san.interfaces.coded_tool import CodedTool
import json
import logging
from datetime import datetime

class GuardianTool(CodedTool):
    """
    Guardian Tool for Industrial IoT Monitoring
    Protects by enforcing approvals and human-in-the-loop safety.
    Focuses on temperature, humidity, pressure, and vibration safety.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    def invoke(self, args, sly_data):
        """
        Main function to handle approvals and safety workflows
        """
        try:
            action_description = args.get("action_description")
            severity = args.get("severity")
            approver_role = args.get("approver_role", "supervisor")
            context_data = args.get("context_data", {})
            approval_required_for = args.get("approval_required_for", "safety_concern")
            consequences_if_denied = args.get("consequences_if_denied", "Safety risk may increase")
            
            self.logger.info(f"Processing {severity} approval request: {action_description}")
            
            # Process approval based on severity
            approval_result = self._process_approval(
                action_description, severity, approver_role, context_data,
                approval_required_for, consequences_if_denied
            )
            
            return {
                "success": True,
                "approval_result": approval_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in invoke: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _process_approval(self, action_description, severity, approver_role, context_data,
                         approval_required_for, consequences_if_denied):
        """Process approval workflow based on severity"""
        
        # Broadcast alert based on severity
        alert_message = self._broadcast_alert(severity, action_description)
        
        # Determine approval workflow
        if severity == "warning":
            return self._handle_warning_approval(
                action_description, approver_role, context_data,
                approval_required_for, consequences_if_denied, alert_message
            )
        elif severity in ["critical", "emergency"]:
            return self._handle_critical_emergency_approval(
                severity, action_description, context_data, alert_message
            )
        else:
            return self._handle_normal_approval(action_description, alert_message)
    
    def _broadcast_alert(self, severity, action_description):
        """Broadcast audio alert based on severity"""
        if severity == "warning":
            alert_message = f"WARNING DETECTED. {action_description}. Supervisor approval required."
        elif severity == "critical":
            alert_message = f"CRITICAL DETECTED. {action_description}. Auto-approved for safety."
        elif severity == "emergency":
            alert_message = f"EMERGENCY DETECTED. {action_description}. Auto-approved for safety."
        else:
            alert_message = f"NOTIFICATION. {action_description}."
        
        self.logger.info(f"Broadcasting alert: {alert_message}")
        return alert_message
    
    def _handle_warning_approval(self, action_description, approver_role, context_data,
                                approval_required_for, consequences_if_denied, alert_message):
        """Handle warning level approval workflow"""
        return {
            "workflow_type": "warning_approval",
            "alert_broadcast": alert_message,
            "approval_required": True,
            "approver_role": approver_role,
            "approval_prompt": {
                "action": action_description,
                "reason": approval_required_for,
                "consequences_if_denied": consequences_if_denied,
                "context": context_data
            },
            "approval_status": "pending_supervisor_input",
            "next_steps": [
                "Display approve/deny prompt to supervisor",
                "Wait for supervisor decision",
                "Log approval decision for audit",
                "Proceed based on supervisor decision"
            ],
            "safety_considerations": [
                "Monitor situation while waiting for approval",
                "Prepare emergency procedures if situation worsens",
                "Document all actions taken"
            ]
        }
    
    def _handle_critical_emergency_approval(self, severity, action_description, context_data, alert_message):
        """Handle critical/emergency level approval workflow"""
        return {
            "workflow_type": "critical_emergency_approval",
            "alert_broadcast": alert_message,
            "approval_required": False,
            "auto_approval": True,
            "approval_status": "auto_approved",
            "approval_reason": f"Auto-approved for safety due to {severity} severity",
            "immediate_actions": [
                "Proceed with safety measures immediately",
                "Notify all relevant personnel",
                "Document auto-approval decision",
                "Monitor situation closely"
            ],
            "safety_considerations": [
                "Safety is the top priority",
                "All personnel should be aware of the situation",
                "Emergency procedures may be required",
                "Document all actions for investigation"
            ]
        }
    
    def _handle_normal_approval(self, action_description, alert_message):
        """Handle normal level approval workflow"""
        return {
            "workflow_type": "normal_approval",
            "alert_broadcast": alert_message,
            "approval_required": False,
            "approval_status": "approved",
            "approval_reason": "Normal operation - no approval required",
            "next_steps": [
                "Continue normal monitoring",
                "Document the notification",
                "No immediate action required"
            ],
            "safety_considerations": [
                "Continue standard safety protocols",
                "Monitor for any changes in conditions",
                "Maintain normal operational procedures"
            ]
        } 