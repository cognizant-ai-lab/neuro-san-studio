import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Appointment:
    patient_id: str
    doctor_id: str
    datetime: datetime.datetime
    type: str
    status: str = "scheduled"

@dataclass
class Medication:
    name: str
    dosage: str
    frequency: str
    start_date: datetime.date
    end_date: Optional[datetime.date] = None

class AppointmentScheduler:
    def __init__(self):
        self.appointments = []
        self.availability = {}
    
    def schedule_appointment(self, patient_id: str, doctor_id: str, 
                           preferred_date: str, appointment_type: str) -> Dict:
        """Schedule a medical appointment"""
        try:
            # Parse date and check availability
            requested_date = datetime.datetime.strptime(preferred_date, "%Y-%m-%d %H:%M")
            
            # Check if slot is available
            if self.is_slot_available(doctor_id, requested_date):
                appointment = Appointment(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    datetime=requested_date,
                    type=appointment_type
                )
                self.appointments.append(appointment)
                return {
                    "success": True,
                    "appointment_id": len(self.appointments),
                    "message": f"Appointment scheduled for {requested_date}"
                }
            else:
                return {
                    "success": False,
                    "message": "Requested slot not available",
                    "alternatives": self.get_alternative_slots(doctor_id, requested_date)
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def is_slot_available(self, doctor_id: str, datetime: datetime.datetime) -> bool:
        """Check if appointment slot is available"""
        # Implementation for checking availability
        return True  # Simplified for demo
    
    def get_alternative_slots(self, doctor_id: str, preferred_date: datetime.datetime) -> List[str]:
        """Get alternative appointment slots"""
        alternatives = []
        for i in range(1, 4):
            alt_date = preferred_date + datetime.timedelta(days=i)
            alternatives.append(alt_date.strftime("%Y-%m-%d %H:%M"))
        return alternatives

class MedicationManager:
    def __init__(self):
        self.medications = {}
        self.reminders = {}
    
    def add_medication(self, patient_id: str, medication: Dict) -> Dict:
        """Add medication to patient's profile"""
        if patient_id not in self.medications:
            self.medications[patient_id] = []
        
        med = Medication(
            name=medication["name"],
            dosage=medication["dosage"],
            frequency=medication["frequency"],
            start_date=datetime.date.today()
        )
        
        self.medications[patient_id].append(med)
        
        return {
            "success": True,
            "message": f"Medication {med.name} added successfully"
        }
    
    def get_medication_reminders(self, patient_id: str) -> List[Dict]:
        """Get current medication reminders for patient"""
        if patient_id not in self.medications:
            return []
        
        reminders = []
        for med in self.medications[patient_id]:
            reminders.append({
                "medication": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "next_dose": self.calculate_next_dose(med)
            })
        
        return reminders
    
    def calculate_next_dose(self, medication: Medication) -> str:
        """Calculate when next dose is due"""
        # Simplified calculation
        return "Next dose in 4 hours"

class HealthKnowledgeBase:
    def __init__(self):
        self.health_tips = {
            "general": [
                "Drink at least 8 glasses of water daily",
                "Get 7-9 hours of sleep each night",
                "Exercise for at least 30 minutes daily",
                "Eat a balanced diet with fruits and vegetables"
            ],
            "nutrition": [
                "Include lean proteins in every meal",
                "Choose whole grains over refined grains",
                "Limit processed foods and added sugars"
            ],
            "exercise": [
                "Start with 10-minute walks if you're sedentary",
                "Incorporate strength training twice a week",
                "Try yoga for flexibility and stress relief"
            ]
        }
    
    def get_health_tips(self, category: str = "general") -> List[str]:
        """Get health tips by category"""
        return self.health_tips.get(category, self.health_tips["general"])
    
    def search_health_info(self, query: str) -> Dict:
        """Search health information"""
        # Simplified search functionality
        return {
            "query": query,
            "results": ["General health information related to your query"],
            "disclaimer": "This information is for educational purposes only. Consult your healthcare provider for medical advice."
        }