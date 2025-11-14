import autogen
from tools.healthcare_tools import AppointmentScheduler, MedicationManager, HealthKnowledgeBase

class HealthcareMultiAgentSystem:
    def __init__(self, config):
        self.config = config
        self.appointment_scheduler = AppointmentScheduler()
        self.medication_manager = MedicationManager()
        self.health_kb = HealthKnowledgeBase()
        
        # Initialize agents
        self.scheduler_agent = autogen.AssistantAgent(
            name="SchedulerAgent",
            system_message="""You are a Healthcare Scheduling Agent. 
            Handle appointment scheduling, rescheduling, and availability checks.
            Always maintain patient privacy and provide clear communication.""",
            llm_config={"model": "gpt-4o"}
        )
        
        self.medication_agent = autogen.AssistantAgent(
            name="MedicationAgent", 
            system_message="""You are a Medication Management Agent.
            Provide medication reminders, check interactions, and maintain adherence.
            Always remind users to consult healthcare providers for medical decisions.""",
            llm_config={"model": "gpt-4o"}
        )
        
        self.health_advisor = autogen.AssistantAgent(
            name="HealthAdvisor",
            system_message="""You are a Health Advisory Agent.
            Provide general health tips, wellness advice, and preventive care information.
            Always include disclaimers about consulting healthcare professionals.""",
            llm_config={"model": "gpt-4o"}
        )
        
        self.coordinator = autogen.AssistantAgent(
            name="Coordinator",
            system_message="""You are the Healthcare Coordinator.
            Route patient queries to appropriate agents and ensure comprehensive care.
            Maintain conversation context and escalate complex cases.""",
            llm_config={"model": "gpt-4o"}
        )
        
        # Register functions with agents
        self.register_functions()
    
    def register_functions(self):
        """Register healthcare functions with appropriate agents"""
        @self.scheduler_agent.register_for_execution()
        @self.coordinator.register_for_llm(description="Schedule medical appointments")
        def schedule_appointment(patient_id: str, doctor_id: str, preferred_date: str, appointment_type: str):
            return self.appointment_scheduler.schedule_appointment(patient_id, doctor_id, preferred_date, appointment_type)
        
        @self.medication_agent.register_for_execution()
        @self.coordinator.register_for_llm(description="Get medication reminders")
        def get_medication_reminders(patient_id: str):
            return self.medication_manager.get_medication_reminders(patient_id)
        
        @self.health_advisor.register_for_execution()
        @self.coordinator.register_for_llm(description="Get health tips")
        def get_health_tips(category: str = "general"):
            return self.health_kb.get_health_tips(category)

    def start_conversation(self, user_message: str):
        """Start a conversation with the healthcare system"""
        user_proxy = autogen.UserProxyAgent(
            name="Patient",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False
        )
        
        # Create group chat
        groupchat = autogen.GroupChat(
            agents=[user_proxy, self.coordinator, self.scheduler_agent, 
                   self.medication_agent, self.health_advisor],
            messages=[],
            max_round=10
        )
        
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config={"model": "gpt-4o"})
        
        # Start the conversation
        user_proxy.initiate_chat(manager, message=user_message)