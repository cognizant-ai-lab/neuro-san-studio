Healthcare Assistant Agent Network
Overview
The Healthcare Assistant is a multi-agent system built with AutoGen and integrated with Neuro SAN, providing appointment scheduling, medication reminders, and health tips for patients. It demonstrates Neuro SAN’s HOCON-based configuration and AAOSA protocol in a healthcare context.
Agents

Scheduler Agent: Manages medical appointments using AppointmentScheduler.
Medication Agent: Handles medication reminders with MedicationManager.
Health Advisor Agent: Provides health tips via HealthKnowledgeBase.
Coordinator Agent: Routes queries to appropriate agents.

Setup

Clone the repository and checkout the PR branch:git clone https://github.com/Idk507/neuro-san-studio.git
cd neuro-san-studio
git fetch origin pull/135/head:pr-135
git checkout pr-135


Set up a virtual environment:python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
export PYTHONPATH=`pwd`   # Windows: set PYTHONPATH=%cd%


Install dependencies:pip install -r requirements.txt


Set environment variables:echo "OPENAI_API_KEY=your-openai-api-key" > .env
export AGENT_MANIFEST_FILE=./registries/healthcare_assistant.hocon
export AGENT_TOOL_PATH=./coded_tools

For Windows:echo OPENAI_API_KEY=your-openai-api-key > .env
set AGENT_MANIFEST_FILE=.\registries\healthcare_assistant.hocon
set AGENT_TOOL_PATH=.\coded_tools



Usage
Run the application:
python coded_tools/healthcare-assistant/main.py

Example input:
Schedule an appointment for patient123 with doctor456 on 2025-06-12 10:00 for a checkup, set a reminder for Aspirin 100mg daily at 8:00 AM, and provide a nutrition tip.

Example output:
Appointment scheduled for 2025-06-12 10:00:00
Medication reminder for Aspirin added successfully
Health tip: Include lean proteins in every meal

Testing

Run unit tests:python -m unittest tests/test_healthcare_tools.py


Verify data persistence in coded_tools/healthcare-assistant/data/appointments.json and medications.json.
Optional: Test with Neuro SAN’s nsflow client:python -m nsflow.client

Access at http://127.0.0.1:4173.

Neuro SAN Integration
Uses registries/healthcare_assistant.hocon with AAOSA protocol, compatible with Neuro SAN’s nsflow client.
Files

registries/healthcare_assistant.hocon: Agent network configuration.
coded_tools/healthcare-assistant/agents/healthcare_agents.py: Agent implementations.
coded_tools/healthcare-assistant/tools/healthcare_tools.py: Tools for scheduling, medication, and health tips.
coded_tools/healthcare-assistant/main.py: Main script.
tests/test_healthcare_tools.py: Unit tests.
coded_tools/healthcare-assistant/data/appointments.json: Appointment storage.
coded_tools/healthcare-assistant/data/medications.json: Medication storage.

Future Improvements

Implement additional tools (e.g., calendar_checker).
Add encryption for HIPAA compliance using sly_data.
Develop a web interface with Flask/FastAPI.

