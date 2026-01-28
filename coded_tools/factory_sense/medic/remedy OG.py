# factory_sense_new/medic/remedy.py
from neuro_san.interfaces.coded_tool import CodedTool
import json
from datetime import datetime
import logging

class MedicTool(CodedTool):
    """
    Medic Tool for Industrial IoT Systems
    Provides remedies and fixes for temperature, humidity, pressure, and vibration issues.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    def invoke(self, args, sly_data):
        """
        Main function to provide remedies and fixes for machine issues
        """
        try:
            machine_id = args.get("machine_id")
            issue_type = args.get("issue_type")
            severity = args.get("severity")
            current_metrics = args.get("current_metrics", {})
            recommended_actions = args.get("recommended_actions", [])
            trend_analysis = args.get("trend_analysis", {})
            root_cause_analysis = args.get("root_cause_analysis", {})
            safety_considerations = args.get("safety_considerations", [])
            
            self.logger.info(f"Providing remedies for {issue_type} on machine {machine_id}")
            
            # Generate remedy based on issue type and severity
            remedy = self._generate_remedy(
                machine_id, issue_type, severity, current_metrics,
                recommended_actions, trend_analysis, root_cause_analysis, safety_considerations
            )
            
            return {
                "success": True,
                "machine_id": machine_id,
                "issue_type": issue_type,
                "severity": severity,
                "remedy": remedy,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in invoke: {e}")
            return {
                "error": str(e),
                "machine_id": machine_id,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _generate_remedy(self, machine_id, issue_type, severity, current_metrics, 
                        recommended_actions, trend_analysis, root_cause_analysis, safety_considerations):
        """Generate detailed remedy based on issue type and severity"""
        
        remedy = {
            "immediate_actions": [],
            "short_term_solutions": [],
            "long_term_prevention": [],
            "safety_precautions": [],
            "required_resources": [],
            "timeline": {},
            "verification_steps": [],
            "root_cause_analysis": root_cause_analysis,
            "trend_analysis": trend_analysis
        }
        
        # Generate remedy based on issue type
        if "temperature" in issue_type.lower():
            remedy.update(self._temperature_remedy(issue_type, severity, current_metrics))
        elif "humidity" in issue_type.lower():
            remedy.update(self._humidity_remedy(issue_type, severity, current_metrics))
        elif "pressure" in issue_type.lower():
            remedy.update(self._pressure_remedy(issue_type, severity, current_metrics))
        elif "vibration" in issue_type.lower():
            remedy.update(self._vibration_remedy(issue_type, severity, current_metrics))
        else:
            remedy.update(self._general_remedy(issue_type, severity, current_metrics))
        
        # Add safety considerations
        remedy["safety_precautions"].extend(safety_considerations)
        
        # Add recommended actions if provided
        if recommended_actions:
            remedy["immediate_actions"].extend(recommended_actions)
        
        return remedy
    
    def _temperature_remedy(self, issue_type, severity, current_metrics):
        """Generate temperature-specific remedies"""
        temperature = current_metrics.get("temperature", 0)
        
        remedy = {
            "immediate_actions": [],
            "short_term_solutions": [],
            "long_term_prevention": [],
            "required_resources": [],
            "timeline": {},
            "verification_steps": []
        }
        
        if "high" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check if cooling system is operational",
                "Verify air circulation around equipment",
                "Check for blocked vents or filters",
                "Monitor temperature trend for rapid changes"
            ]
            
            remedy["short_term_solutions"] = [
                "Clean or replace air filters",
                "Increase ventilation in the area",
                "Check cooling system coolant levels",
                "Verify thermostat settings",
                "Check for heat-generating equipment nearby"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular cooling system maintenance schedule",
                "Install additional temperature monitoring points",
                "Consider upgrading cooling capacity",
                "Implement automated temperature alerts",
                "Review equipment placement for optimal airflow"
            ]
            
            remedy["required_resources"] = [
                "HVAC technician",
                "Temperature monitoring equipment",
                "Cleaning supplies for filters",
                "Cooling system maintenance tools"
            ]
            
            remedy["timeline"] = {
                "immediate": "0-15 minutes",
                "short_term": "1-4 hours",
                "long_term": "1-2 weeks"
            }
            
            remedy["verification_steps"] = [
                "Verify temperature drops below warning threshold",
                "Confirm cooling system is maintaining stable temperature",
                "Check that temperature remains stable for 30+ minutes",
                "Verify all monitoring systems are functioning"
            ]
        
        elif "low" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check if heating system is operational",
                "Verify insulation integrity",
                "Check for drafts or air leaks",
                "Monitor temperature trend for rapid changes"
            ]
            
            remedy["short_term_solutions"] = [
                "Adjust heating system settings",
                "Seal any air leaks or drafts",
                "Check insulation for damage",
                "Verify thermostat calibration"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular heating system maintenance",
                "Improve building insulation",
                "Install temperature monitoring alerts",
                "Review building envelope for efficiency"
            ]
        
        remedy["safety_precautions"] = [
            "Wear appropriate thermal protection when working near hot equipment",
            "Ensure proper ventilation when working with heating systems",
            "Use lockout/tagout procedures when servicing equipment",
            "Have fire extinguisher available when working with heating systems"
        ]
        
        return remedy
    
    def _humidity_remedy(self, issue_type, severity, current_metrics):
        """Generate humidity-specific remedies"""
        humidity = current_metrics.get("humidity", 0)
        
        remedy = {
            "immediate_actions": [],
            "short_term_solutions": [],
            "long_term_prevention": [],
            "required_resources": [],
            "timeline": {},
            "verification_steps": []
        }
        
        if "high" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check dehumidification system operation",
                "Verify ventilation is adequate",
                "Look for water leaks or condensation",
                "Check for sources of moisture"
            ]
            
            remedy["short_term_solutions"] = [
                "Increase dehumidification capacity",
                "Improve ventilation in the area",
                "Fix any water leaks",
                "Remove sources of excess moisture",
                "Check drainage systems"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular dehumidification maintenance",
                "Install humidity monitoring alerts",
                "Improve building moisture barriers",
                "Review HVAC system for humidity control",
                "Implement moisture source management"
            ]
            
            remedy["required_resources"] = [
                "HVAC technician",
                "Dehumidification equipment",
                "Moisture detection tools",
                "Ventilation improvement materials"
            ]
        
        elif "low" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check humidification system operation",
                "Verify system water levels",
                "Check for system leaks",
                "Monitor humidity trend"
            ]
            
            remedy["short_term_solutions"] = [
                "Adjust humidification settings",
                "Check and refill water reservoirs",
                "Clean humidification equipment",
                "Verify system calibration"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular humidification maintenance",
                "Install humidity monitoring alerts",
                "Review system capacity requirements",
                "Implement automated humidity control"
            ]
        
        remedy["safety_precautions"] = [
            "Ensure proper electrical safety when working with humidification equipment",
            "Use appropriate PPE when handling water systems",
            "Follow lockout/tagout procedures for electrical work",
            "Be aware of slip hazards from condensation"
        ]
        
        return remedy
    
    def _pressure_remedy(self, issue_type, severity, current_metrics):
        """Generate pressure-specific remedies"""
        pressure = current_metrics.get("pressure", 0)
        
        remedy = {
            "immediate_actions": [],
            "short_term_solutions": [],
            "long_term_prevention": [],
            "required_resources": [],
            "timeline": {},
            "verification_steps": []
        }
        
        if "high" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check for pressure relief valve operation",
                "Verify system pressure settings",
                "Look for pressure regulator issues",
                "Check for system blockages"
            ]
            
            remedy["short_term_solutions"] = [
                "Adjust pressure regulator settings",
                "Clean or replace pressure relief valves",
                "Check for system leaks",
                "Verify pump operation",
                "Check for system blockages"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular pressure system maintenance",
                "Install pressure monitoring alerts",
                "Review system design for pressure management",
                "Implement automated pressure control"
            ]
            
            remedy["required_resources"] = [
                "Pressure system technician",
                "Pressure monitoring equipment",
                "Pressure relief valve tools",
                "System maintenance supplies"
            ]
        
        elif "low" in issue_type.lower():
            remedy["immediate_actions"] = [
                "Check pump operation",
                "Verify system pressure settings",
                "Look for system leaks",
                "Check for air in the system"
            ]
            
            remedy["short_term_solutions"] = [
                "Repair or replace faulty pumps",
                "Fix system leaks",
                "Bleed air from the system",
                "Check pressure regulator settings",
                "Verify system integrity"
            ]
            
            remedy["long_term_prevention"] = [
                "Implement regular pump maintenance",
                "Install pressure monitoring alerts",
                "Review system design for pressure requirements",
                "Implement leak detection systems"
            ]
        
        remedy["safety_precautions"] = [
            "Use appropriate pressure-rated equipment and tools",
            "Follow lockout/tagout procedures for pressure systems",
            "Wear appropriate PPE when working with pressurized systems",
            "Ensure proper pressure relief before maintenance"
        ]
        
        return remedy
    
    def _vibration_remedy(self, issue_type, severity, current_metrics):
        """Generate vibration-specific remedies"""
        vibration = current_metrics.get("vibration", 0)
        
        remedy = {
            "immediate_actions": [],
            "short_term_solutions": [],
            "long_term_prevention": [],
            "required_resources": [],
            "timeline": {},
            "verification_steps": []
        }
        
        remedy["immediate_actions"] = [
            "Check equipment mounting and fasteners",
            "Verify equipment alignment",
            "Look for loose components",
            "Check for bearing wear or damage"
        ]
        
        remedy["short_term_solutions"] = [
            "Tighten all mounting bolts and fasteners",
            "Realign equipment if necessary",
            "Replace worn bearings",
            "Check for mechanical wear",
            "Verify equipment balance"
        ]
        
        remedy["long_term_prevention"] = [
            "Implement regular vibration monitoring",
            "Schedule preventive maintenance for bearings",
            "Install vibration monitoring equipment",
            "Implement equipment alignment procedures",
            "Review equipment mounting design"
        ]
        
        remedy["required_resources"] = [
            "Mechanical technician",
            "Vibration analysis equipment",
            "Alignment tools",
            "Bearing replacement tools",
            "Mounting hardware"
        ]
        
        remedy["timeline"] = {
            "immediate": "0-30 minutes",
            "short_term": "2-8 hours",
            "long_term": "1-4 weeks"
        }
        
        remedy["verification_steps"] = [
            "Measure vibration levels after repairs",
            "Verify equipment runs smoothly",
            "Check for unusual noises",
            "Monitor vibration levels over time",
            "Confirm equipment alignment"
        ]
        
        remedy["safety_precautions"] = [
            "Use lockout/tagout procedures when working on equipment",
            "Wear appropriate PPE for mechanical work",
            "Ensure equipment is properly secured before maintenance",
            "Follow proper lifting procedures for heavy components"
        ]
        
        return remedy
    
    def _general_remedy(self, issue_type, severity, current_metrics):
        """Generate general remedies for unknown issue types"""
        remedy = {
            "immediate_actions": [
                "Document the issue and current conditions",
                "Check system logs for errors",
                "Verify all connections and power supplies",
                "Contact technical support if needed"
            ],
            "short_term_solutions": [
                "Perform system diagnostics",
                "Check for software updates",
                "Verify system configuration",
                "Review maintenance records"
            ],
            "long_term_prevention": [
                "Implement regular system monitoring",
                "Schedule preventive maintenance",
                "Install diagnostic tools",
                "Review system design"
            ],
            "required_resources": [
                "Technical support",
                "Diagnostic equipment",
                "System documentation",
                "Maintenance tools"
            ],
            "timeline": {
                "immediate": "0-30 minutes",
                "short_term": "1-4 hours",
                "long_term": "1-2 weeks"
            },
            "verification_steps": [
                "Verify issue resolution",
                "Test system functionality",
                "Monitor system performance",
                "Document resolution steps"
            ],
            "safety_precautions": [
                "Follow all safety procedures",
                "Use appropriate PPE",
                "Follow lockout/tagout procedures",
                "Document all work performed"
            ]
        }
        
        return remedy 