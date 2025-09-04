import os
from pyhocon import ConfigFactory
from coded_tools.healthcare_assistant.agents.healthcare_agents import HealthcareMultiAgentSystem
from dotenv import load_dotenv

def main():
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env file")

    try:
        config = ConfigFactory.parse_file("registries/healthcare_assistant.hocon")
    except Exception as e:
        raise ValueError(f"Failed to parse HOCON config: {str(e)}")

    healthcare_system = HealthcareMultiAgentSystem(config)

    user_message = (
        "Schedule an appointment for patient123 with Dr. Smith on 2025-06-01 10:00 for a checkup, "
        "set a reminder for Aspirin 100mg daily at 8:00 AM, and provide a nutrition tip."
    )
    healthcare_system.start_conversation(user_message)

if __name__ == "__main__":
    main()