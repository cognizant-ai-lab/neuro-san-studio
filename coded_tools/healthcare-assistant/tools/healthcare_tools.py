import datetime
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Appointment:
    patient_id: str
    doctor_id: str
    datetime: datetime.datetime
    type: str
    status: str = "scheduled"

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "datetime": self.datetime.isoformat(),
            "type": self.type,
            "status": self.status
        }

@dataclass
class Medication:
    name: str
    dosage: str
    frequency: str
    start_date: datetime.date
    end_date: Optional[datetime.date] = None

    def to_dict(self):
        return {
            "name": self.name,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None
        }

class AppointmentScheduler:
    def __init__(self):
        self.appointments = []
        self.availability = {}
        self.data_path = os.path.join("coded_tools", "healthcare-assistant", "data", "appointments.json")
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        self.load_appointments()

    def load_appointments(self):
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
                self.appointments = [
                    Appointment(
                        patient_id=appt["patient_id"],
                        doctor_id=appt["doctor_id"],
                        datetime=datetime.datetime.fromisoformat(appt["datetime"]),
                        type=appt["type"],
                        status=appt["status"]
                    ) for appt in data
                ]
        except FileNotFoundError:
            self.appointments = []
            self.save_appointments()

    def save_appointments(self):
        with open(self.data_path, "w") as f:
            json.dump([appt.to_dict() for appt in self.appointments], f, indent=2)

    def schedule_appointment(self, patient_id: str, doctor_id: str, 
                           preferred_date: str, appointment_type: str) -> Dict:
        try:
            requested_date = datetime.datetime.strptime(preferred_date, "%Y-%m-%d %H:%M")
            if self.is_slot_available(doctor_id, requested_date):
                appointment = Appointment(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    datetime=requested_date,
                    type=appointment_type
                )
                self.appointments.append(appointment)
                self.save_appointments()
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
        return not any(appt.doctor_id == doctor_id and appt.datetime == datetime 
                      for appt in self.appointments)

    def get_alternative_slots(self, doctor_id: str, preferred_date: datetime.datetime) -> List[str]:
        alternatives = []
        for i in range(1, 4):
            alt_date = preferred_date + datetime.timedelta(days=i)
            if self.is_slot_available(doctor_id, alt_date):
                alternatives.append(alt_date.strftime("%Y-%m-%d %H:%M"))
        return alternatives

class MedicationManager:
    def __init__(self):
        self.medications = {}
        self.reminders = {}
        self.data_path = os.path.join("coded_tools", "healthcare-assistant", "data", "medications.json")
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        self.load_medications()

    def load_medications(self):
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
                for patient_id, meds in data.items():
                    self.medications[patient_id] = [
                        Medication(
                            name=med["name"],
                            dosage=med["dosage"],
                            frequency=med["frequency"],
                            start_date=datetime.date.fromisoformat(med["start_date"]),
                            end_date=datetime.date.fromisoformat(med["end_date"]) if med["end_date"] else None
                        ) for med in meds
                    ]
        except FileNotFoundError:
            self.medications = {}
            self.save_medications()

    def save_medications(self):
        with open(self.data_path, "w") as f:
            data = {pid: [med.to_dict() for med in meds] for pid, meds in self.medications.items()}
            json.dump(data, f, indent=2)

    def add_medication(self, patient_id: str, medication: Dict) -> Dict:
        if patient_id not in self.medications:
            self.medications[patient_id] = []
        med = Medication(
            name=medication["name"],
            dosage=medication["dosage"],
            frequency=medication["frequency"],
            start_date=datetime.date.today()
        )
        self.medications[patient_id].append(med)
        self.save_medications()
        return {
            "success": True,
            "message": f"Medication {med.name} added successfully"
        }

    def get_medication_reminders(self, patient_id: str) -> List[Dict]:
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
        if medication.frequency == "daily":
            return (datetime.datetime.now() + datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
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
        return self.health_tips.get(category, self.health_tips["general"])

    def search_health_info(self, query: str) -> Dict:
        return {
            "query": query,
            "results": ["General health information related to your query"],
            "disclaimer": "This information is for educational purposes only. Consult your healthcare provider."
        }