import os
from pyhocon import ConfigFactory
from agents.healthcare_agents import HealthcareMultiAgentSystem
from dotenv import load_dotenv

def main():
    # Load environment variables
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in .env file")

    # Load HOCON config
    config = ConfigFactory.parse_file("configs/healthcare_assistant.hocon")

    # Initialize LLM config
    llm_config = {
        "config_list": [
            {
                "model": "gpt-4o",
                "api_key": os.getenv("OPENAI_API_KEY")
            }
        ]
    }

    # Update config with LLM details
    for agent in config["healthcare_assistant.agents"]:
        agent["llm_config"] = llm_config

    # Initialize the multi-agent system
    healthcare_system = HealthcareMultiAgentSystem(config)

    # Example user interaction
    user_message = (
        "Schedule an appointment for patient123 with Dr. Smith on 2025-06-01 10:00 for a checkup, "
        "set a reminder for Aspirin 100mg daily at 8:00 AM, and provide a nutrition tip."
    )
    healthcare_system.start_conversation(user_message)

if __name__ == "__main__":
    main()