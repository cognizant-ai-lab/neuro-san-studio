import unittest
import json
from coded_tools.healthcare_assistant.tools.healthcare_tools import AppointmentScheduler, MedicationManager, HealthKnowledgeBase
from datetime import datetime

class TestHealthcareTools(unittest.TestCase):
    def setUp(self):
        self.scheduler = AppointmentScheduler()
        self.med_manager = MedicationManager()
        self.health_kb = HealthKnowledgeBase()

    def test_schedule_appointment(self):
        result = self.scheduler.schedule_appointment(
            patient_id="patient123",
            doctor_id="doctor456",
            preferred_date="2025-06-12 10:00",
            appointment_type="checkup"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Appointment scheduled for 2025-06-12 10:00:00")
        with open("coded_tools/healthcare-assistant/data/appointments.json", "r") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["patient_id"], "patient123")

    def test_add_medication(self):
        result = self.med_manager.add_medication(
            patient_id="patient123",
            medication={"name": "Aspirin", "dosage": "100mg", "frequency": "daily"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Medication Aspirin added successfully")
        with open("coded_tools/healthcare-assistant/data/medications.json", "r") as f:
            data = json.load(f)
            self.assertIn("patient123", data)
            self.assertEqual(data["patient123"][0]["name"], "Aspirin")

    def test_get_health_tips(self):
        tips = self.health_kb.get_health_tips("nutrition")
        self.assertTrue(len(tips) > 0)
        self.assertIn("Include lean proteins in every meal", tips)

if __name__ == "__main__":
    unittest.main()